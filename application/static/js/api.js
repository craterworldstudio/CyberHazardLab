async function apiRequest(method, path, body = null) {

    const options = {
        method: method,
        headers: {
            "Content-Type": "application/json"
        }
    };

    if (body !== null) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(path, options);

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.error || `API request failed: ${response.status}`
        );
    }

    return data;
}
document.addEventListener("DOMContentLoaded", () => { 
    




});