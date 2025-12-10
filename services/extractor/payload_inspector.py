"""
Payload Inspector Utility

Utility script to fetch sample payloads from APIs and save them for inspection.
Helps identify actual field names and structure before finalizing data models.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .jsearch_client import JSearchClient
from .glassdoor_client import GlassdoorClient

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class PayloadInspector:
    """
    Utility for inspecting API payloads.
    
    Fetches sample data from APIs and saves to files for manual inspection.
    """
    
    def __init__(
        self,
        output_dir: str = "payload_samples",
        jsearch_api_key: Optional[str] = None,
        glassdoor_api_key: Optional[str] = None
    ):
        """
        Initialize the payload inspector.
        
        Args:
            output_dir: Directory to save payload samples
            jsearch_api_key: JSearch API key (reads from env if None)
            glassdoor_api_key: Glassdoor API key (reads from env if None)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        jsearch_key = jsearch_api_key or os.getenv('JSEARCH_API_KEY')
        glassdoor_key = glassdoor_api_key or os.getenv('GLASSDOOR_API_KEY')
        
        if jsearch_key:
            self.jsearch_client = JSearchClient(api_key=jsearch_key)
        else:
            self.jsearch_client = None
            logger.warning("JSearch API key not found - JSearch inspection disabled")
        
        if glassdoor_key:
            self.glassdoor_client = GlassdoorClient(api_key=glassdoor_key)
        else:
            self.glassdoor_client = None
            logger.warning("Glassdoor API key not found - Glassdoor inspection disabled")
    
    def inspect_jsearch_payload(
        self,
        query: str = "data engineer",
        location: Optional[str] = None,
        country: str = "ca",
        date_posted: str = "week"
    ) -> Dict[str, Any]:
        """
        Fetch and inspect a JSearch API payload.
        
        Args:
            query: Job search query
            location: Job location
            country: Country code
            date_posted: Date window
            
        Returns:
            API response dictionary
        """
        if not self.jsearch_client:
            raise ValueError("JSearch client not initialized - API key required")
        
        logger.info(f"Fetching JSearch payload for query: '{query}'")
        
        response = self.jsearch_client.search_jobs(
            query=query,
            location=location,
            country=country,
            date_posted=date_posted,
            num_pages=1
        )
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"jsearch_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved JSearch payload to: {filename}")
        
        # Print structure summary
        self._print_payload_structure("JSearch", response)
        
        return response
    
    def inspect_glassdoor_payload(
        self,
        query: str = "google"
    ) -> Dict[str, Any]:
        """
        Fetch and inspect a Glassdoor API payload.
        
        Args:
            query: Company name or domain to search for
            
        Returns:
            API response dictionary
        """
        if not self.glassdoor_client:
            raise ValueError("Glassdoor client not initialized - API key required")
        
        logger.info(f"Fetching Glassdoor payload for query: '{query}'")
        
        response = self.glassdoor_client.search_company(query=query)
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"glassdoor_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved Glassdoor payload to: {filename}")
        
        # Print structure summary
        self._print_payload_structure("Glassdoor", response)
        
        return response
    
    def _print_payload_structure(self, api_name: str, payload: Dict[str, Any]):
        """
        Print a summary of the payload structure.
        
        Args:
            api_name: Name of the API
            payload: Payload dictionary
        """
        print(f"\n=== {api_name} Payload Structure ===")
        print(f"Top-level keys: {list(payload.keys())}")
        
        if 'data' in payload and isinstance(payload['data'], list) and len(payload['data']) > 0:
            first_item = payload['data'][0]
            print(f"\nFirst item keys: {list(first_item.keys())}")
            print(f"\nFirst item sample:")
            print(json.dumps(first_item, indent=2, ensure_ascii=False)[:1000])
            if len(json.dumps(first_item, indent=2)) > 1000:
                print("... (truncated)")
        
        print()


def main():
    """Main entry point for running the payload inspector."""
    import argparse
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Inspect API payloads')
    parser.add_argument('--api', choices=['jsearch', 'glassdoor', 'both'], default='both',
                       help='Which API to inspect')
    parser.add_argument('--query', default='data engineer',
                       help='Search query (for JSearch)')
    parser.add_argument('--company', default='google',
                       help='Company name (for Glassdoor)')
    parser.add_argument('--output-dir', default='payload_samples',
                       help='Output directory for payload files')
    
    args = parser.parse_args()
    
    inspector = PayloadInspector(output_dir=args.output_dir)
    
    try:
        if args.api in ['jsearch', 'both']:
            inspector.inspect_jsearch_payload(query=args.query)
        
        if args.api in ['glassdoor', 'both']:
            inspector.inspect_glassdoor_payload(query=args.company)
        
        print("\n=== Inspection Complete ===")
        print(f"Payload files saved to: {args.output_dir}")
        print("Review the JSON files to understand the actual API response structure.")
        
    except Exception as e:
        logger.error(f"Inspection failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
