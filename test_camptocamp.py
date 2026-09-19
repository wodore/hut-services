#!/usr/bin/env python
"""Test script for Camptocamp service."""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hut_services.camptocamp import CamptocampService

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)


def main():
    """Test the Camptocamp service."""
    print("Testing Camptocamp Service")
    print("=" * 50)

    # Initialize service
    service = CamptocampService()

    # Test with a small limit and fetch details
    limit = 3
    print(f"\nFetching {limit} huts with detailed information...")

    try:
        huts = service.get_huts_from_source(
            limit=limit,
            fetch_details=True,
            request_interval=0.5,  # Be nice to the API
        )

        print(f"\nSuccessfully fetched {len(huts)} huts\n")

        for idx, hut_source in enumerate(huts, 1):
            print(f"\n{'='*50}")
            print(f"Hut {idx}/{len(huts)}")
            print(f"{'='*50}")

            try:
                # Convert to HutSchema
                hut = service.convert(hut_source, include_photos=False)

                print(f"Name: {hut.name.i18n}")
                if hut.name.fr:
                    print(f"  French: {hut.name.fr}")
                if hut.name.en:
                    print(f"  English: {hut.name.en}")
                if hut.name.de:
                    print(f"  German: {hut.name.de}")

                print("\nLocation:")
                print(f"  Lat: {hut.location.lat}")
                print(f"  Lon: {hut.location.lon}")
                print(f"  Elevation: {hut.location.ele}m")

                print("\nCapacity:")
                if hut.capacity.if_open:
                    print(f"  Open/Unstaffed: {hut.capacity.if_open}")
                if hut.capacity.if_closed:
                    print(f"  Staffed: {hut.capacity.if_closed}")

                if hut.owner:
                    print(f"\nOwner/Custodian: {hut.owner.name}")

                if hut.contacts and len(hut.contacts) > 0 and hut.contacts[0].phone:
                    print(f"Phone: {hut.contacts[0].phone}")

                print(f"\nType: {hut.hut_type.if_open}")
                print(f"URL: {hut.url}")

                if hut.description.i18n:
                    desc = hut.description.i18n[:200]
                    if len(hut.description.i18n) > 200:
                        desc += "..."
                    print(f"\nDescription: {desc}")

                if hut.notes:
                    print(f"\nNotes ({len(hut.notes)}):")
                    for note in hut.notes[:2]:  # Show first 2 notes
                        if note.fr:
                            print(f"  - {note.fr[:100]}...")
                        elif note.en:
                            print(f"  - {note.en[:100]}...")

            except Exception as e:
                print(f"Error converting hut: {e}")
                import traceback

                traceback.print_exc()

    except Exception as e:
        print(f"Error fetching huts: {e}")
        import traceback

        traceback.print_exc()

    print(f"\n{'='*50}")
    print("Test completed!")


if __name__ == "__main__":
    main()
