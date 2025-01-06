from typing import Optional

from duckduckgo_search import DDGS

from omni_webui.retrieval.web.main import SearchResult, get_filtered_results


def search_duckduckgo(
    query: str, count: int, filter_list: Optional[list[str]] = None
) -> list[SearchResult]:
    """
    Search using DuckDuckGo's Search API and return the results as a list of SearchResult objects.
    Args:
        query (str): The query to search for
        count (int): The number of results to return

    Returns:
        list[SearchResult]: A list of search results
    """
    # Use the DDGS context manager to create a DDGS object
    with DDGS() as ddgs:
        # Use the ddgs.text() method to perform the search
        ddgs_gen = ddgs.text(
            query, safesearch="moderate", max_results=count, backend="api"
        )
        # Check if there are search results
        if ddgs_gen:
            # Convert the search results into a list
            search_results = [r for r in ddgs_gen]

    # Create an empty list to store the SearchResult objects
    results = []
    # Iterate over each search result
    for result in search_results:
        # Create a SearchResult object and append it to the results list
        results.append(
            SearchResult(
                link=result["href"],
                title=result.get("title"),
                snippet=result.get("body"),
            )
        )
    if filter_list:
        results = get_filtered_results(results, filter_list)
    # Return the list of search results
    return results
