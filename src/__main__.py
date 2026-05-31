from .cli import main

if __name__ == "__main__":
    import sys
    import asyncio
    sys.exit(asyncio.run(main()))
