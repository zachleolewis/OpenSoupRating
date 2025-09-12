#!/usr/bin/env python3
"""
Command-line interface for Open Soup Rating (OSR) System
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional, List

import open_soup_rating as osr


def main():
    """Main CLI entry point for the OSR system."""
    parser = argparse.ArgumentParser(
        description="Open Soup Rating (OSR) - Valorant Player Performance Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  osr calculate match_data.json
  osr calculate match_data.json --output ratings.json
  osr calculate match_data.json --components KillContrib DeathContrib
  osr list-components
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Calculate ratings command
    calc_parser = subparsers.add_parser('calculate', help='Calculate player ratings from match data')
    calc_parser.add_argument('input_file', help='Path to match data JSON file')
    calc_parser.add_argument('-o', '--output', help='Output file path (default: stdout)')
    calc_parser.add_argument('-w', '--weights', help='Path to custom weights JSON file')
    calc_parser.add_argument('-n', '--normalization', help='Path to custom normalization parameters JSON file')
    calc_parser.add_argument('-c', '--components', nargs='+', help='Specific components to use')
    calc_parser.add_argument('--config', help='Path to configuration directory')
    calc_parser.add_argument('--pretty', action='store_true', help='Pretty print JSON output')
    
    # List components command
    list_parser = subparsers.add_parser('list-components', help='List available rating components')
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == 'calculate':
            return handle_calculate(args)
        elif args.command == 'list-components':
            return handle_list_components()
        elif args.command == 'version':
            return handle_version()
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_calculate(args) -> int:
    """Handle the calculate command."""
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        return 1
    
    # Load optional configuration files
    weights = None
    if args.weights:
        try:
            with open(args.weights, 'r') as f:
                weights = json.load(f)
        except Exception as e:
            print(f"Error loading weights file: {e}", file=sys.stderr)
            return 1
    
    normalization_params = None
    if args.normalization:
        try:
            with open(args.normalization, 'r') as f:
                normalization_params = json.load(f)
        except Exception as e:
            print(f"Error loading normalization file: {e}", file=sys.stderr)
            return 1
    
    try:
        # Calculate ratings
        result = osr.calculate_rating(
            match_data=args.input_file,
            weights=weights,
            normalization_params=normalization_params,
            components_to_use=args.components,
            config_path=args.config
        )
        
        # Format output
        output_data = result
        if args.pretty:
            output_str = json.dumps(output_data, indent=2, ensure_ascii=False)
        else:
            output_str = json.dumps(output_data, ensure_ascii=False)
        
        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Ratings saved to {args.output}")
        else:
            print(output_str)
        
        return 0
        
    except Exception as e:
        print(f"Error calculating ratings: {e}", file=sys.stderr)
        return 1


def handle_list_components() -> int:
    """Handle the list-components command."""
    try:
        components = osr.list_components()
        print("Available rating components:")
        for component in components:
            print(f"  - {component}")
        return 0
    except Exception as e:
        print(f"Error listing components: {e}", file=sys.stderr)
        return 1


def handle_version() -> int:
    """Handle the version command."""
    print(f"Open Soup Rating (OSR) v{osr.__version__}")
    print(f"Author: {osr.__author__}")
    print(f"License: {osr.__license__}")
    return 0


if __name__ == '__main__':
    sys.exit(main())