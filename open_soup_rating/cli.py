#!/usr/bin/env python3
"""
Command-line interface for Open Soup Rating (OSR) System
"""

import sys
import argparse
import json
from pathlib import Path
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
  osr calculate matches/ --aggregate --pretty
  osr calculate match_data.json --components KillSwing DeathSwing
  osr list-components
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Calculate ratings command
    calc_parser = subparsers.add_parser('calculate', help='Calculate player ratings from match data')
    calc_parser.add_argument('input_file', help='Path to a match JSON file (.json/.json.gz) or a directory of them')
    calc_parser.add_argument('-o', '--output', help='Output file path (default: stdout)')
    calc_parser.add_argument('-c', '--components', nargs='+', help='Components to report alongside the rating')
    calc_parser.add_argument('-a', '--aggregate', action='store_true',
                             help='Combine all matches into one shrunk rating per player')
    calc_parser.add_argument('--role-adjusted', action='store_true',
                             help='With --aggregate, rate players against their role baseline')
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
    
    try:
        # Calculate ratings
        result = osr.calculate_rating_with_player_info(
            match_data=args.input_file,
            components_to_use=args.components,
            config_path=args.config
        )
        if args.aggregate:
            result = osr.aggregate_ratings(result, config_path=args.config, role_adjusted=args.role_adjusted)
            result = dict(sorted(result.items(), key=lambda kv: kv[1]['rating'], reverse=True))
        
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