const defaultRequestConfig = {
	mode: "cors",
	credentials: "same-origin",
	redirect: "follow",
	referrerPolicy: "no-referrer-when-downgrade",
};

class Ajax {
	/**
	 * Ajax - A TypeScript module for simplifying AJAX requests.
	 *
	 * This module provides an easy-to-use interface for making HTTP requests (GET, POST, PUT, DELETE, PATCH)
	 * and handling responses from the server. It uses the Fetch API under the hood and offers additional
	 * functionality like automatic JSON handling, URL parameter support, request timeouts, and default headers.
	 *
	 * Features:
	 * - Simplified methods for common HTTP requests.
	 * - Configurable global and per-request headers.
	 * - Support for URL parameters.
	 * - Timeout handling for requests.
	 * - Supports aborting requests using AbortController.
	 * - Offers both Promise-based API.
	 *
	 *  @example
	 *  // Basic Usage Example:
	 *
	 *  // Initialize the module with default configuration
	 *  const ajax = new Ajax({ baseURL: 'https://api.example.com' });
	 *
	 *  // Performing a GET request
	 *  ajax.get('/path/to/resource')
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Performing a POST request
	 *  ajax.post('/path/to/resource', { key: 'value' })
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Performing a PUT request
	 *  ajax.put('/path/to/resource/123', { updatedKey: 'updatedValue' })
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Performing a DELETE request
	 *  ajax.delete('/path/to/resource/123')
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Performing a PATCH request
	 *  ajax.patch('/path/to/resource/123', { patchedKey: 'patchedValue' })
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Setting a default header
	 *  ajax.setDefaultHeader('Authorization', 'Bearer token');
	 *
	 *  // Advanced Usage Example:
	 *
	 *  // Using URL parameters and custom headers
	 *  ajax.get('/path/to/resource', {
	 *      params: { query: 'searchQuery' },
	 *      headers: { 'Custom-Header': 'value' }
	 *  })
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error(error));
	 *
	 *  // Handling timeouts
	 *  ajax.get('/path/to/resource', { timeout: 5000 }) // 5 seconds timeout
	 *      .then(response => console.log(response))
	 *      .catch(error => console.error('Request timed out', error));
	 *
	 *  // Aborting a request
	 *  const controller = new AbortController();
	 *  ajax.get('/path/to/resource', { signal: controller.signal })
	 *      .catch(error => console.error('Request aborted', error));
	 *  controller.abort(); // Abort the request
	 */
	constructor(defaultConfig = { baseURL: "", headers: {}, timeout: 5000, requestConfig: defaultRequestConfig }) {
		this.defaultConfig = {
			baseURL: defaultConfig.baseURL,
			headers: defaultConfig.headers,
			timeout: defaultConfig.timeout,
			requestConfig: { ...defaultRequestConfig, ...defaultConfig.requestConfig },
		};
	}

	// Combines base URL and relative URL into a full URL, ensuring exactly one slash between them.
	combineURLs(baseURL, relativeURL) {
		if (!baseURL) return relativeURL;
		return baseURL.replace(/\/+$/, "") + "/" + relativeURL.replace(/^\/+/, "");
	}

	// Helper method to perform the actual HTTP request
	async request(method, url, data = null, options = {}) {
		if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
			if (!this.hasCSRFToken()) throw new Error("CSRFToken is missing in the headers.");
		}

		let fullUrl;

		try {
			fullUrl = new URL(this.combineURLs(this.defaultConfig.baseURL, url));
		} catch (e) {
			fullUrl = url;
		}

		// Append URL parameters if provided
		if (options.params) {
			Object.keys(options.params).forEach((key) => fullUrl.searchParams.append(key, options.params[key].toString()));
		}

		const config = {
			method: method,
			headers: { ...this.defaultConfig.headers, ...options.headers },
			...this.defaultConfig.requestConfig,
			signal: options.signal,
		};

		// If method is not GET, add body data
		if (method !== "GET" && data) {
			config.body = data instanceof FormData ? data : JSON.stringify(data);
		}

		// Handle request timeout
		if (this.defaultConfig.timeout > 0 || options.timeout) {
			const controller = new AbortController();
			config.signal = controller.signal;
			setTimeout(() => controller.abort(), options.timeout || this.defaultConfig.timeout);
		}

		try {
			const response = await fetch(fullUrl.toString(), config);
			const responseData = await response.json();
			if (!response.ok) {
				throw new Error(responseData.message || "Error in request");
			}
			return responseData;
		} catch (error) {
			throw error;
		}
	}

	// Performs a GET request to the specified URL.
	get(url, options) {
		return this.request("GET", url, null, options);
	}

	// Performs a POST request to the specified URL with the provided data.
	post(url, data, options) {
		return this.request("POST", url, data, options);
	}

	// Performs a PUT request to update data at the specified URL.
	put(url, data, options) {
		return this.request("PUT", url, data, options);
	}

	// Performs a DELETE request to remove data from the specified URL.
	delete(url, options) {
		return this.request("DELETE", url, null, options);
	}

	// Performs a PATCH request to partially update data at the specified URL.
	patch(url, data, options) {
		return this.request("PATCH", url, data, options);
	}

	// Sets a default header that will be included in all requests.
	setDefaultHeader(header, value) {
		this.defaultConfig.headers[header] = value;
	}

	// Removes a default header.
	removeDefaultHeader(header) {
		delete this.defaultConfig.headers[header];
	}

	// Check if X-CSRFToken is present in the headers.
	hasCSRFToken() {
		return this.defaultConfig.headers["X-CSRFToken"] !== undefined;
	}
}

const ajax = new Ajax({
	headers: {
		"X-Requested-With": "XMLHttpRequest",
	},
});

export default ajax;
