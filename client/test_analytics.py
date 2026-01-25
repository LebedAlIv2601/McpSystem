"""Test script for Analytics MCP server."""

import asyncio
import json
import logging
from analytics_manager import AnalyticsManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Test analytics manager."""
    logger.info("=== Testing Analytics MCP Server ===")

    manager = AnalyticsManager()

    try:
        # Start server
        logger.info("\n1. Starting Analytics MCP server...")
        await manager.start()

        # Test get_statistics
        logger.info("\n2. Testing get_statistics...")
        stats = await manager.get_statistics()
        print("\nStatistics:")
        print(json.dumps(stats, ensure_ascii=False, indent=2))

        # Test analyze_errors
        logger.info("\n3. Testing analyze_errors...")
        errors = await manager.analyze_errors()
        print("\nErrors Analysis:")
        print(json.dumps(errors, ensure_ascii=False, indent=2))

        # Test analyze_funnel
        logger.info("\n4. Testing analyze_funnel...")
        funnel = await manager.analyze_funnel()
        print("\nFunnel Analysis:")
        print(json.dumps(funnel, ensure_ascii=False, indent=2))

        # Test analyze_dropoff
        logger.info("\n5. Testing analyze_dropoff...")
        dropoff = await manager.analyze_dropoff()
        print("\nDropoff Analysis:")
        print(json.dumps(dropoff, ensure_ascii=False, indent=2))

        # Test get_user_journey
        logger.info("\n6. Testing get_user_journey for user_001...")
        journey = await manager.get_user_journey("user_001")
        print("\nUser Journey:")
        print(json.dumps(journey, ensure_ascii=False, indent=2))

        logger.info("\n=== All tests completed successfully ===")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        # Stop server
        logger.info("\nStopping Analytics MCP server...")
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
