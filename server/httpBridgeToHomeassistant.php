// input_number.firebeetle_esp32_wetterdisplay_bad_aktualisierungsdauer
// input_number.firebeetle_esp32_wetterdisplay_bad_batterie
// input_number.firebeetle_esp32_wetterdisplay_bad_batterie_spannung

// curl -X POST http://192.168.1.10/httpBridgeToHomeassistant.php -H "Content-Type: application/json" -d '[{"entity_id": "input_number.firebeetle_esp32_wetterdisplay_bad_aktualisierungsdauer", "value": 13},{"entity_id": "input_number.firebeetle_esp32_wetterdisplay_bad_batterie", "value": 37},{"entity_id": "input_number.firebeetle_esp32_wetterdisplay_bad_batterie_spannung", "value": 1337}]'

<?php
// Home Assistant API configuration
$ha_url = "https://your-homeassistant-url:8123/api/services/input_number/set_value";
$ha_token = "YOUR_HA_TOKEN"; // Replace with your Home Assistant token

// Read incoming JSON data from the ESP32
$request_body = file_get_contents('php://input');
$data = json_decode($request_body, true);

if (is_array($data)) {
    $responses = [];
    foreach ($data as $item) {
        // Validate and process each entity_id and value pair
        if (isset($item['entity_id']) && isset($item['value'])) {
            $entity_id = $item['entity_id'];
            $value = $item['value'];

            // JSON payload for input_number.set_value
            $payload = json_encode([
                'entity_id' => $entity_id,
                'value' => $value
            ]);

            // Send cURL request to Home Assistant
            $ch = curl_init($ha_url);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_TIMEOUT, 2); // Timeout 2 seconds
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                "Authorization: Bearer $ha_token",
                "Content-Type: application/json",
            ]);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

            curl_close($ch);

            // Store the result
            $responses[] = [
                "entity_id" => $entity_id,
                "success" => $http_code === 200,
                "message" => $http_code === 200 ? "Value successfully sent" : "Error forwarding to Home Assistant"
            ];
        } else {
            $responses[] = [
                "entity_id" => $item['entity_id'] ?? 'unknown',
                "success" => false,
                "message" => "Invalid data"
            ];
        }
    }

    // Return JSON response with all results
    echo json_encode($responses);
} else {
    echo json_encode(["success" => false, "message" => "Invalid data structure"]);
}