# Illumio App Dpndr command line tool

This CLI tool provides powerful traffic analysis and visualization capabilities for Illumio PolicyComputeEngine (PCE) data. It allows users to generate various types of traffic graphs based on PCE data, offering insights into network flows and application communications.

## Examples

### Sankey Diagram
![Sankey Diagram](../examples/examples_sankey.png)

### Sunburst Diagram
![Sunburst Diagram](../examples/examples_sunburst.png)

### Graphviz Directed Graph
![Graphviz Directed Graph](../examples/examples_graphviz.png)

## Features

- Fetch traffic flow data from Illumio PCE
- Generate traffic graphs in multiple formats:
  - Sankey diagrams
  - Sunburst diagrams
  - Graphviz directed graphs
- Customize date ranges for analysis
- Export graphs in various formats (HTML, PNG, JPG, SVG)
- Limit the number of traffic flows to analyze
- Flexible graph orientation options

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/alexgoller/illumio-app-dpndr
   cd illumio-app-dpndr/cli
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

The main command for the CLI tool is `traffic`. Here's the basic syntax:

```
python cli.py traffic [OPTIONS]
```

### Options

- `--pce-host`: PCE host (required)
- `--port`: PCE port (required)
- `--org-id`: Organization ID (required)
- `--api-key`: API key (required)
- `--api-secret`: API secret (required)
- `--start`: Start date (YYYY-MM-DD or "X days ago", default: "30 days ago")
- `--end`: End date (YYYY-MM-DD or "today", default: "today")
- `--output`: Output filename without extension (default: "traffic_graph")
- `--format`: Output format (html, png, jpg, svg, default: html)
- `--diagram-type`: Diagram type (sankey, sunburst, graphviz, default: sankey)
- `--direction`: Flow directed graph orientation (LR left-right, TB top-bottom, default: LR)
- `--limit`: Maximum number of traffic flows to fetch (default: 2000)

### Example

Generate a Sankey diagram of traffic flows for the last 7 days:

```
python cli.py traffic --pce-host your-pce-host --port 8443 --org-id 1 --api-key your-api-key --api-secret your-api-secret --start "7 days ago" --diagram-type sankey --format html
```

This will generate an HTML file named `traffic_graph.html` containing the Sankey diagram of traffic flows.

## Output

The tool generates a graph visualization based on the specified options. The output file will be saved in the current directory with the name specified by the `--output` option and the appropriate extension based on the `--format` option.

## Dependencies

This tool relies on several Python libraries, including:

- click
- pandas
- numpy
- illumio
- plotly
- kaleido
- networkx
- matplotlib
- pygraphviz

Ensure all dependencies are installed using the `requirements.txt` file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.