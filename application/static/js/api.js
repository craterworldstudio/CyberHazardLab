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

    let data;
    try {
        data = await response.json();
    } catch (e) {
        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }
        return null;
    }

    if (!response.ok) {
        throw new Error(
            (data && data.error) || `API request failed: ${response.status}`
        );
    }

    return data;
}
document.addEventListener("DOMContentLoaded", () => { 
    




});