#!/usr/bin/env python3

import os
import json
import click
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from illumio import PolicyComputeEngine, TrafficQuery
from collections import defaultdict
import plotly.graph_objects as go
import plotly.express as px
from kaleido.scopes.plotly import PlotlyScope
import networkx as nx
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')  # Use non-interactive backend
import pygraphviz as pgv
import networkx as nx
import io

label_href_map = {}
value_href_map = {}

def parse_date(date_string):
	if date_string.lower() == 'today':
		return datetime.now()
	if date_string.lower().endswith(' ago'):
		days = int(date_string.split()[0])
		return datetime.now() - timedelta(days=days)
	return datetime.strptime(date_string, "%Y-%m-%d")

def traffic_flow_unique_name(flow):
	return "{}-{}_{}-{}_{}".format(
		flow.src.ip,
		flow.dst.ip,
		flow.service.port,
		flow.service.proto,
		flow.flow_direction
	)

def to_dataframe(flows):
	global label_href_map
	global value_href_map
	
	series_array = []
	
	for flow in flows:
		f = {
			'src_ip': flow.src.ip,
			'src_hostname': flow.src.workload.name if flow.src.workload is not None else None,
			'dst_ip': flow.dst.ip,
			'dst_hostname': flow.dst.workload.name if flow.dst.workload is not None else None,
			'proto': flow.service.proto,
			'port': flow.service.port,
			'process_name': flow.service.process_name,
			'service_name': flow.service.service_name,
			'user_name': flow.service.user_name,
			'windows_service_name': flow.service.windows_service_name,
			'policy_decision': flow.policy_decision,
			'flow_direction': flow.flow_direction,
			'num_connections': flow.num_connections,
			'first_detected': flow.timestamp_range.first_detected,
			'last_detected': flow.timestamp_range.last_detected
		}
		
		if flow.src.workload:
			for l in flow.src.workload.labels:
				if l.href in label_href_map:
					f['src_' + label_href_map[l.href]['key']] = label_href_map[l.href]['value']
		
		if flow.dst.workload:
			for l in flow.dst.workload.labels:
				if l.href in label_href_map:
					f['dst_' + label_href_map[l.href]['key']] = label_href_map[l.href]['value']
		
		series_array.append(f)
	
	return pd.DataFrame(series_array)

def generate_traffic_graph(df, diagram_type, output_format, direction):
	connections = defaultdict(lambda: defaultdict(int))

	for _, row in df.iterrows():
		src = f"{row['src_app']} ({row['src_env']})"
		dst = f"{row['dst_app']} ({row['dst_env']})"
		if src != dst:
			connections[src][dst] += 1
	
	if diagram_type == 'sankey':
		return generate_sankey_diagram(connections, output_format)
	elif diagram_type == 'sunburst':
		return generate_sunburst_diagram(connections, output_format)
	elif diagram_type == 'graphviz':
		return generate_graphviz_diagram(connections, output_format, direction)
	else:
		raise ValueError(f"Unsupported diagram type: {diagram_type}")

def generate_sankey_diagram(connections, output_format):
	sources, targets, values = [], [], []
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
		)
	)])
	
	fig.update_layout(title_text="Application Flow Sankey Diagram", font_size=10)
	
	return export_plotly(fig, output_format)

def generate_sunburst_diagram(connections, output_format):
	data = []
	for source, destinations in connections.items():
		for target, value in destinations.items():
			data.append({
				'source': source,
				'target': target,
				'value': value
			})
	
	df = pd.DataFrame(data)
	
	fig = px.sunburst(
		df,
		path=['source', 'target'],
		values='value',
		title="Application Flow Sunburst Diagram"
	)
	
	return export_plotly(fig, output_format)

def generate_graphviz_diagram(connections, output_format):
	G = nx.DiGraph()
	
	for source, destinations in connections.items():
		for target, weight in destinations.items():
			G.add_edge(source, target, weight=weight)
	
	plt.figure(figsize=(12, 8))
	pos = nx.spring_layout(G)
	nx.draw(G, pos, with_labels=True, node_color='lightblue', 
			node_size=3000, font_size=8, font_weight='bold')
	
	edge_labels = nx.get_edge_attributes(G, 'weight')
	nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
	
	plt.title("Application Flow Graph")
	
	if output_format == 'html':
		raise ValueError("HTML output is not supported for Graphviz diagrams")
	else:
		buf = io.BytesIO()
		plt.savefig(buf, format=output_format)
		buf.seek(0)
		return buf.getvalue()

def generate_graphviz_diagram(connections, output_format, direction):
	# Create a new pygraphviz graph
	if direction != 'LR' and direction != 'TB':
		direction = 'LR'

	A = pgv.AGraph(directed=True, strict=True, rankdir=direction) 
	
	# Add nodes and edges
	for source, destinations in connections.items():
		for target, weight in destinations.items():
			A.add_edge(source, target, weight=weight)
	
	# Set graph attributes for better layout
	A.graph_attr.update(
		dpi="300",
		fontsize="10",
		size="8,8",  # in inches
		ratio="fill",
		margin="0.5,0.5",
	)
	
	# Set node attributes
	A.node_attr.update(
		shape="box",
		style="filled",
		fillcolor="lightblue",
		fontsize="8",
	)
	
	# Set edge attributes
	A.edge_attr.update(
		fontsize="8",
		len="1.5",  # Adjust edge length to reduce overlapping
	)
	
	# Apply the layout
	A.layout(prog="dot")  # 'dot' creates a hierarchical layout
	
	if output_format == 'html':
		raise ValueError("HTML output is not supported for Graphviz diagrams")
	else:
		# Save to a BytesIO object
		buf = io.BytesIO()
		A.draw(buf, format=output_format, prog='dot')
		buf.seek(0)
		return buf.getvalue()

def export_plotly(fig, output_format):
	if output_format == 'html':
		return fig.to_html(include_plotlyjs=True, full_html=True)
	else:
		scope = PlotlyScope()
		img_bytes = scope.transform(fig, format=output_format)
		return img_bytes

@click.group()
def cli():
	"""Illumio CLI tool for traffic analysis and visualization."""
	pass

@cli.command()
@click.option('--depth', type=int, default=2, help='Depth of the tree map (1 for protocol only, 2 for protocol and port)')
# Add other options similar to the 'traffic' command
def treemap(depth, **kwargs):
	"""Generate a tree map of traffic flows ordered by IP protocol and ports."""
	pass
	
@cli.command()
@click.option('--top', type=int, default=10, help='Number of top traffic flows to display')
@click.option('--metric', type=click.Choice(['connections', 'bytes']), default='connections', help='Metric to use for ranking')
# Add other options similar to the 'traffic' command
def top_traffic(top, metric, **kwargs):
	"""Analyze and display the top traffic flows."""
	# Implement the top traffic analysis logic here
	pass

@cli.command()
@click.option('--top', type=int, default=10, help='Number of top ports to display')
# Add other options similar to the 'traffic' command
def top_ports(top, **kwargs):
	"""Identify and display the top ports used in traffic."""
	# Implement the top ports analysis logic here
	pass

@cli.command()
@click.option('--pce-host', required=True, help='PCE host')
@click.option('--port', required=True, type=int, help='PCE port')
@click.option('--org-id', required=True, help='Organization ID')
@click.option('--api-key', required=True, help='API key')
@click.option('--api-secret', required=True, help='API secret')
@click.option('--start', default='30 days ago', help='Start date (YYYY-MM-DD or "X days ago")')
@click.option('--end', default='today', help='End date (YYYY-MM-DD or "X days ago")')
@click.option('--output', default='traffic_graph', help='Output filename (without extension)')
@click.option('--format', type=click.Choice(['html', 'png', 'jpg', 'svg']), default='html', help='Output format')
@click.option('--diagram-type', type=click.Choice(['sankey', 'sunburst', 'graphviz']), default='sankey', help='Diagram type')
@click.option('--direction', type=click.Choice(['LR', 'TB']), default='LR', help='Flow directed graph orientation (LR left-right, TB top-bottom)')
@click.option('--limit', type=int, default=2000, help='Maximum number of traffic flows to fetch')
def traffic(pce_host, port, org_id, api_key, api_secret, start, end, output, format, diagram_type, direction, limit):
	"""Generate traffic graph based on Illumio PCE data."""
	global label_href_map
	global value_href_map

	pce = PolicyComputeEngine(pce_host, port=port, org_id=org_id)
	pce.set_credentials(api_key, api_secret)

	if not pce.check_connection():
		click.echo("Connection to PCE failed.")
		return

	for l in pce.labels.get():
		label_href_map[l.href] = {"key": l.key, "value": l.value}
		value_href_map["{}={}".format(l.key, l.value)] = l.href

	d_end = parse_date(end) if end != 'today' else datetime.now()
	d_start = parse_date(start)

	traffic_query = TrafficQuery.build(
		start_date=d_start.strftime("%Y-%m-%d"),
		end_date=d_end.strftime("%Y-%m-%d"),
		include_services=[],
		exclude_services=[
			{"port": 53},
			{"port": 137},
			{"port": 138},
			{"port": 139},
			{"proto": "udp"}
		],
		exclude_destinations=[
			{"transmission": "broadcast"},
			{"transmission": "multicast"}
		],
		policy_decisions=['allowed', 'potentially_blocked'],
		max_results=limit
	)

	all_traffic = pce.get_traffic_flows_async(
		query_name='all-traffic',
		traffic_query=traffic_query
	)

	df = to_dataframe(all_traffic)
	
	content = generate_traffic_graph(df, diagram_type, format, direction)
	
	filename = f"{output}.{format}"
	if format == 'html':
		with open(filename, 'w') as f:
			f.write(content)
	else:
		with open(filename, 'wb') as f:
			f.write(content)
	
	click.echo(f"Traffic graph saved as {filename}")

if __name__ == '__main__':
	cli()
