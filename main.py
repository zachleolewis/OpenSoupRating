#!/usr/bin/env python3
# Open Soup Rating (OSR) System - Main Entry Point
# A modular, extensible rating system for Valorant player performance analysis.

import sys
import os
from pathlib import Path

# Add the package to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    # Main entry point for the OSR system.
    print("Open Soup Rating (OSR) System v1.1.0")
    print("=" * 40)
    print("Calculate Valorant player ratings from match data")
    print()

    try:
        # Import the library
        import open_soup_rating as osr

        print("Library loaded successfully!")
        print(f"Available components: {osr.list_components()}")
        print()

        # Interactive mode
        print("Choose an option:")
        print("1. Calculate ratings from match data")
        print("2. Get individual components")
        print("3. List available components")
        print("4. Exit")
        print()

        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            match_dir = input("Enter path to match data directory: ").strip().strip('"\'')
            if os.path.exists(match_dir):
                print("Calculating ratings...")
                ratings = osr.calculate_rating_with_player_info(match_dir)
                print(f"Calculated ratings for {len(ratings)} player-matches")

                # Save results to root folder
                output_file = "ratings_output.json"
                osr.data.loader.save_data(ratings, output_file)
                print(f"Results saved to {output_file}")
            else:
                print(f"Directory '{match_dir}' does not exist!")

        elif choice == '2':
            match_dir = input("Enter path to match data directory: ").strip().strip('"\'')
            component = input("Enter component name (or 'all' for all components): ").strip()

            if os.path.exists(match_dir):
                if component.lower() == 'all':
                    components = None
                else:
                    components = component

                print("Calculating components...")
                component_data = osr.get_components(match_dir, components)
                print(f"Calculated components for {len(component_data)} player-matches")

                # Save results to root folder
                output_file = f"components_{component}_output.json"
                osr.data.loader.save_data(component_data, output_file)
                print(f"Results saved to {output_file}")
            else:
                print(f"Directory '{match_dir}' does not exist!")

        elif choice == '3':
            components = osr.list_components()
            print("Available components:")
            for comp in components:
                print(f"  - {comp}")

        elif choice == '4':
            print("Goodbye!")
            return

        else:
            print("Invalid choice!")

    except ImportError as e:
        print(f"Failed to import library: {e}")
        print("Make sure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
