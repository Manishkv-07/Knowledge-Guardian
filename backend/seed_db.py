import sys
from pathlib import Path

# Add backend directory to PYTHONPATH
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.services.memory_manager import memory_manager

def main():
    print("=== Seeding Demo Database Data ===")
    try:
        memory_manager.seed_demo_data_if_empty()
        print("Success! Database has been seeded with sample documents and stored insights.")
    except Exception as e:
        print(f"Error during seeding: {e}")

if __name__ == "__main__":
    main()
