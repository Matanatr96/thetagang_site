class DataFetchError(Exception):
    """Exception raised for errors in fetching data from an API."""

    def __init__(self, ticker: str, status_code: int, response_text: str):
        self.ticker = ticker
        self.status_code = status_code
        self.response_text = response_text
        self.message = f"Error fetching data for {ticker}: HTTP {status_code}"
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message}\nResponse text: {self.response_text}"