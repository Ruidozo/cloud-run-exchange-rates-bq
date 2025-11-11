"""Tests for Open Exchange Rates API integration."""
from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from app.oxr import fetch_historical_rates


class TestFetchHistoricalRates:
    """Test suite for OXR API fetching."""
    
    def test_missing_api_key(self):
        """Test error when API key is not provided."""
        test_date = date(2025, 11, 10)
        
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                fetch_historical_rates(test_date)
            
            assert "OXR_APP_ID" in str(exc_info.value)
    
    @patch('requests.get')
    def test_successful_fetch(self, mock_get):
        """Test successful API fetch."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "base": "USD",
            "rates": {
                "EUR": 0.92,
                "USD": 1.0,
                "GBP": 0.81
            }
        }
        mock_get.return_value = mock_response
        
        result = fetch_historical_rates(test_date, app_id="test_key")
        
        # Verify request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "2025-11-10" in call_args[0][0]
        assert "app_id=test_key" in call_args[0][0]
        
        # Verify response
        assert result["base"] == "USD"
        assert "EUR" in result["rates"]
    
    @patch('requests.get')
    def test_http_404_error(self, mock_get):
        """Test handling of 404 error (date not available)."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=1)
    
    @patch('requests.get')
    def test_http_401_error_no_retry(self, mock_get):
        """Test that 401 (unauthorized) is not retried."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_historical_rates(test_date, app_id="invalid_key", max_retries=3)
        
        # Should only be called once (no retries for 4xx)
        assert mock_get.call_count == 1
    
    @patch('requests.get')
    def test_http_429_rate_limit(self, mock_get):
        """Test handling of 429 rate limit error."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=1)
    
    @patch('requests.get')
    def test_http_500_error_with_retry(self, mock_get):
        """Test that 500 errors are retried."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=3)
        
        # Should retry 3 times for 5xx errors
        assert mock_get.call_count == 3
    
    @patch('requests.get')
    @patch('time.sleep')
    def test_retry_with_exponential_backoff(self, mock_sleep, mock_get):
        """Test retry logic uses exponential backoff."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=3)
        
        # Verify exponential backoff (2, 4, 8 seconds)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2  # Sleeps between attempts
        assert sleep_calls[0] == 2  # First retry
        assert sleep_calls[1] == 4  # Second retry
    
    @patch('requests.get')
    def test_timeout_error(self, mock_get):
        """Test handling of timeout errors."""
        test_date = date(2025, 11, 10)
        
        mock_get.side_effect = requests.Timeout("Connection timeout")
        
        with pytest.raises(requests.Timeout):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=2)
        
        # Should retry on timeout
        assert mock_get.call_count == 2
    
    @patch('requests.get')
    def test_connection_error(self, mock_get):
        """Test handling of connection errors."""
        test_date = date(2025, 11, 10)
        
        mock_get.side_effect = requests.ConnectionError("Network unreachable")
        
        with pytest.raises(requests.ConnectionError):
            fetch_historical_rates(test_date, app_id="test_key", max_retries=2)
        
        # Should retry on connection error
        assert mock_get.call_count == 2
    
    @patch('requests.get')
    def test_eventual_success_after_retries(self, mock_get):
        """Test successful fetch after initial failures."""
        test_date = date(2025, 11, 10)
        
        # First two calls fail, third succeeds
        failure_response = Mock()
        failure_response.status_code = 503
        failure_response.raise_for_status.side_effect = requests.HTTPError(response=failure_response)
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "base": "USD",
            "rates": {"EUR": 0.92}
        }
        
        mock_get.side_effect = [failure_response, failure_response, success_response]
        
        result = fetch_historical_rates(test_date, app_id="test_key", max_retries=3)
        
        # Should eventually succeed
        assert result["base"] == "USD"
        assert mock_get.call_count == 3
    
    @patch('requests.get')
    def test_invalid_json_response(self, mock_get):
        """Test handling of invalid JSON in response."""
        test_date = date(2025, 11, 10)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError):
            fetch_historical_rates(test_date, app_id="test_key")
    
    def test_date_formatting(self):
        """Test that date is formatted correctly in URL."""
        test_date = date(2025, 1, 5)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"base": "USD", "rates": {}}
            mock_get.return_value = mock_response
            
            fetch_historical_rates(test_date, app_id="test_key")
            
            # Check URL contains correct date format
            call_url = mock_get.call_args[0][0]
            assert "2025-01-05" in call_url
    
    def test_timeout_parameter(self):
        """Test that timeout is passed to requests."""
        test_date = date(2025, 11, 10)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"base": "USD", "rates": {}}
            mock_get.return_value = mock_response
            
            fetch_historical_rates(test_date, app_id="test_key")
            
            # Verify timeout is set
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs.get('timeout') == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])