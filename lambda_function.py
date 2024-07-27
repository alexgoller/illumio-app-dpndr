import os
import json
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from illumio import *
from collections import defaultdict
import plotly.graph_objects as go


s3 = boto3.client('s3')
BUCKET_NAME = os.environ['S3_BUCKET_NAME']

label_href_map = {}
value_href_map = {}

def traffic_flow_unique_name(flow):
	return "{}-{}_{}-{}_{}".format(
		flow.src.ip,
		flow.dst.ip,
		flow.service.port,
		flow.service.proto,
		flow.flow_direction
	)

def to_dataframe(flows) -> pd.DataFrame:
	print("In to_dataframe")
	print(len(flows))
	series_array = []
	
	for flow in flows:
		# rebuild it here in a loop so to break
		f = {}
		f['src_ip'] = flow.src.ip,
		f['src_hostname'] = flow.src.workload.name if flow.src.workload is not None else None
		if flow.src.workload:
			for l in flow.src.workload.labels:
				if l.href in label_href_map:
					# print(label_href_map[l.href])
					f['src_' + label_href_map[l.href]['key']] = label_href_map[l.href]['value']
					
		f['dst_ip'] = flow.dst.ip,
		f['dst_hostname'] = flow.src.workload.name if flow.src.workload is not None else None
		if flow.dst.workload:
			for l in flow.dst.workload.labels:
				if l.href in label_href_map:
					# print(label_href_map[l.href])
					f['dst_' + label_href_map[l.href]['key']] = label_href_map[l.href]['value']

		f['proto'] = flow.service.proto
		f['port'] = flow.service.port
		f['process_name'] = flow.service.process_name
		f['service_name'] = flow.service.service_name
		f['user_name']    = flow.service.user_name
		f['windows_service_name'] = flow.service.windows_service_name
		f['policy_decision'] = flow.policy_decision
		f['flow_direction'] = flow.flow_direction
		f['num_connections'] = flow.num_connections
		f['first_detected'] = flow.timestamp_range.first_detected
		f['last_detected'] = flow.timestamp_range.last_detected
		series_array.append(f)
	
	df = pd.DataFrame(series_array)        
	return df

def lambda_handler(event, context):
	try:
		# Parse input parameters
		body = json.loads(event['body'])
		pce_host = body['pce_host']
		pce_port = int(body['port'])
		org_id = body['org_id']
		api_key = body['api_key']
		api_secret = body['api_secret']
		
		print(f'PCE Host: {pce_host}	Port: {pce_port}	Org ID: {org_id}	API Key: {api_key}')
		# Get traffic data from your API
		pce = PolicyComputeEngine(pce_host, port=pce_port, org_id = org_id)
		pce.set_credentials(api_key, api_secret)

		if pce.check_connection():
			print("Connection to PCE successful")
		else:
			print(f'Connection to PCE failed: {pce_host} {pce_port} {org_id} {api_key}')


		# fill label dict, this reads all labels and puts the object into a value of a dict. The dict key is the label name.
		for l in pce.labels.get():
			label_href_map[l.href] = { "key": l.key, "value": l.value }
			value_href_map["{}={}".format(l.key, l.value)] = l.href

		print(f'Label Href Map: {label_href_map}')

		# use a start date and subtract a month of it using a timedelta object
		month = timedelta(days=30)
		d_end   = datetime.now()
		d_end_f = d_end.strftime("%Y-%m-%d")

		d_start = d_end - month
		d_start_f = d_start.strftime("%Y-%m-%d")

		print(f'Start Date: {d_start_f}	End Date: {d_end_f}')

		# be sure to limit the query to a finite number of elements for testing here. (max_results = 10)
		traffic_query = TrafficQuery.build(
				start_date = d_start_f,
				end_date = d_end_f,
				include_services = [],
				exclude_services = [
					{ "port": 53 },
					{ "port": 137 },
					{ "port": 138 },
					{ "port": 139 },
					{ "proto": "udp" }
				],
				exclude_destinations = [
					{
						"transmission": "broadcast"
					},
					{
						"transmission": "multicast"
					}
				],
				policy_decisions = ['allowed', 'blocked', 'potentially_blocked'],
				max_results = 1000
			)


		all_traffic = pce.get_traffic_flows_async(
			query_name = 'all-traffic',
			traffic_query = traffic_query
		)

		print(f'All Traffic: {len(all_traffic)}')

		df = to_dataframe(all_traffic)
		print(f'Converted to dataframe: {df.shape}')

		connections = defaultdict(lambda: defaultdict(int))

		#### TODO
		# Process each row in the DataFrame
		for _, row in df.iterrows():
			src = f"{row['src_app']} ({row['src_env']})"
			dst = f"{row['dst_app']} ({row['dst_env']})"
			connections[src][dst] += 1
		
		# Create lists for Sankey diagram
		sources = []
		targets = []
		values = []
		labels = set()
		
		for source, destinations in connections.items():
			for target, value in destinations.items():
				sources.append(source)
				targets.append(target)
				values.append(value)
				labels.add(source)
				labels.add(target)
		
		labels = list(labels)
		label_to_index = {label: i for i, label in enumerate(labels)}
		
		# Create the Sankey diagram
		fig = go.Figure(data=[go.Sankey(
			node = dict(
			  pad = 15,
			  thickness = 20,
			  line = dict(color = "black", width = 0.5),
			  label = labels,
			  color = "blue"
			),
			link = dict(
			  source = [label_to_index[s] for s in sources],
			  target = [label_to_index[t] for t in targets],
			  value = values
		  ))])
		
		fig.update_layout(title_text="Application Flow Sankey Diagram", font_size=10)
		
		# Save graph as image
		img_bytes = fig.to_image(format="png")
		
		# Upload to S3
		filename = f"graph_{context.aws_request_id}.png"
		s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=img_bytes, ContentType='image/png')
		
		# Generate presigned URL
		url = s3.generate_presigned_url('get_object',
										Params={'Bucket': BUCKET_NAME, 'Key': filename},
										ExpiresIn=3600)
		
		return {
			'statusCode': 200,
			'body': json.dumps({'image_url': url}),
			'headers': {
				'Access-Control-Allow-Origin': '*',
				'Content-Type': 'application/json'
			}
		}
	except Exception as e:
		return {
			'statusCode': 500,
			'body': json.dumps({'error': str(e)}),
			'headers': {
				'Access-Control-Allow-Origin': '*',
				'Content-Type': 'application/json'
			}
		}
