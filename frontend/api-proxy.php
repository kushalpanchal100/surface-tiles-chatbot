<?php
/**
 * Surfaces Tiles UK - Chatbot & Voice Assistant API Proxy
 * 
 * Secure proxy endpoint that relays text and voice requests from client JavaScript
 * to the Python FastAPI RAG & Voice backend.
 * 
 * Capabilities:
 * - Text Chat: POST api-proxy.php?action=chat (or default POST) -> /chat
 * - Voice Chat: POST api-proxy.php?action=voice -> /voice/chat
 * - Standalone TTS: POST api-proxy.php?action=synthesize -> /voice/synthesize
 * - Standalone STT: POST api-proxy.php?action=transcribe -> /voice/transcribe
 * - Health Check: GET api-proxy.php -> /health
 */

// Set JSON headers and CORS headers for safe cross-origin and local testing
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

// Load configuration
$config = require __DIR__ . '/config.php';

// Handle preflight OPTIONS request
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type, Accept');
    http_response_code(204);
    exit;
}

// Allow health check via GET
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $healthUrl = rtrim($config['api_url'], '/') . $config['health_endpoint'];
    $response = forwardRequest('GET', $healthUrl, null, $config['request_timeout']);
    http_response_code($response['status_code']);
    echo $response['body'];
    exit;
}

// Only allow POST for chat and voice requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode([
        'meta' => ['status' => 0, 'message' => 'Method Not Allowed'],
        'data' => ['Response' => 'Invalid request method. Please use POST.'],
        'statusCode' => 405
    ]);
    exit;
}

$action = $_GET['action'] ?? 'chat';

// -------------------------------------------------------------------------
// 1. Action: Voice Chat (Audio -> STT -> RAG -> TTS -> Voice Response)
// -------------------------------------------------------------------------
if ($action === 'voice') {
    $voiceUrl = rtrim($config['api_url'], '/') . ($config['voice_chat_endpoint'] ?? '/voice/chat');

    // Case A: Multipart form upload with audio file
    if (!empty($_FILES['audio']) || !empty($_FILES['file'])) {
        $uploadedFile = !empty($_FILES['audio']) ? $_FILES['audio'] : $_FILES['file'];
        $sessionId = $_POST['session_id'] ?? null;

        if ($uploadedFile['error'] !== UPLOAD_ERR_OK) {
            http_response_code(400);
            echo json_encode([
                'meta' => ['status' => 0, 'message' => 'File upload error: ' . $uploadedFile['error']],
                'data' => ['Response' => 'Audio upload failed.'],
                'statusCode' => 400
            ]);
            exit;
        }

        $postFields = [
            'file' => new CURLFile($uploadedFile['tmp_name'], $uploadedFile['type'] ?: 'audio/webm', $uploadedFile['name'])
        ];
        if ($sessionId) {
            $postFields['session_id'] = $sessionId;
        }

        $backendResponse = forwardMultipart($voiceUrl, $postFields, $config['request_timeout']);
    } else {
        // Case B: JSON body containing base64 audio
        $rawInput = file_get_contents('php://input');
        $backendResponse = forwardRequest('POST', $voiceUrl, $rawInput, $config['request_timeout'], ['Content-Type: application/json']);
    }

    if ($backendResponse['success']) {
        http_response_code($backendResponse['status_code']);
        echo $backendResponse['body'];
    } else {
        http_response_code(503);
        echo json_encode([
            'meta' => ['status' => 0, 'message' => 'Voice backend service unreachable: ' . $backendResponse['error']],
            'data' => [
                'user_transcript' => '',
                'Response' => "I'm having trouble processing voice audio right now. Please feel free to type your question below or browse directly at surfacestiles.co.uk."
            ],
            'statusCode' => 503
        ]);
    }
    exit;
}

// -------------------------------------------------------------------------
// 2. Action: Text-to-Speech Synthesize Only (powers message Read Aloud)
// -------------------------------------------------------------------------
if ($action === 'synthesize') {
    $synthUrl = rtrim($config['api_url'], '/') . ($config['voice_synthesize_endpoint'] ?? '/voice/synthesize');
    $rawInput = file_get_contents('php://input');
    $backendResponse = forwardRequest('POST', $synthUrl, $rawInput, $config['request_timeout'], ['Content-Type: application/json']);

    if ($backendResponse['success']) {
        http_response_code($backendResponse['status_code']);
        echo $backendResponse['body'];
    } else {
        http_response_code(503);
        echo json_encode([
            'meta' => ['status' => 0, 'message' => 'TTS service unreachable: ' . $backendResponse['error']],
            'statusCode' => 503
        ]);
    }
    exit;
}

// -------------------------------------------------------------------------
// 3. Action: Speech-to-Text Transcribe Only
// -------------------------------------------------------------------------
if ($action === 'transcribe') {
    $transcribeUrl = rtrim($config['api_url'], '/') . ($config['voice_transcribe_endpoint'] ?? '/voice/transcribe');
    if (!empty($_FILES['audio']) || !empty($_FILES['file'])) {
        $uploadedFile = !empty($_FILES['audio']) ? $_FILES['audio'] : $_FILES['file'];
        $postFields = [
            'file' => new CURLFile($uploadedFile['tmp_name'], $uploadedFile['type'] ?: 'audio/webm', $uploadedFile['name'])
        ];
        $backendResponse = forwardMultipart($transcribeUrl, $postFields, $config['request_timeout']);
    } else {
        $rawInput = file_get_contents('php://input');
        $backendResponse = forwardRequest('POST', $transcribeUrl, $rawInput, $config['request_timeout'], ['Content-Type: application/json']);
    }

    if ($backendResponse['success']) {
        http_response_code($backendResponse['status_code']);
        echo $backendResponse['body'];
    } else {
        http_response_code(503);
        echo json_encode([
            'meta' => ['status' => 0, 'message' => 'Transcription service unreachable: ' . $backendResponse['error']],
            'statusCode' => 503
        ]);
    }
    exit;
}

// -------------------------------------------------------------------------
// 4. Action: Standard Text Chat (Default)
// -------------------------------------------------------------------------
$rawInput = file_get_contents('php://input');
$inputData = json_decode($rawInput, true);

if (!$inputData || !isset($inputData['message']) || trim($inputData['message']) === '') {
    http_response_code(400);
    echo json_encode([
        'meta' => ['status' => 0, 'message' => 'Bad Request'],
        'data' => ['Response' => 'Message is required and cannot be empty.'],
        'statusCode' => 400
    ]);
    exit;
}

// Sanitize inputs
$message = trim(strip_tags($inputData['message']));
$sessionId = isset($inputData['session_id']) && is_string($inputData['session_id']) ? trim($inputData['session_id']) : null;

if ($sessionId && !preg_match('/^[0-9a-fA-F-]{8,40}$/', $sessionId)) {
    $sessionId = null;
}

// Prepare payload for backend FastAPI
$payload = [
    'message' => $message,
];
if ($sessionId) {
    $payload['session_id'] = $sessionId;
}
if (isset($inputData['history']) && is_array($inputData['history'])) {
    $payload['history'] = array_slice($inputData['history'], -10);
}

// Forward to backend
$chatUrl = rtrim($config['api_url'], '/') . $config['chat_endpoint'];
$backendResponse = forwardRequest('POST', $chatUrl, json_encode($payload), $config['request_timeout'], ['Content-Type: application/json']);

if ($backendResponse['success']) {
    http_response_code($backendResponse['status_code']);
    echo $backendResponse['body'];
} else {
    http_response_code(503);
    echo json_encode([
        'meta' => [
            'status' => 0,
            'message' => 'Backend service unreachable: ' . $backendResponse['error']
        ],
        'data' => [
            'Response' => "I'm having trouble reaching the Surfaces Tiles catalog right now. Please feel free to browse directly at [surfacestiles.co.uk](https://surfacestiles.co.uk) or call our showroom experts at **{$config['help']['contact_phone']}**."
        ],
        'statusCode' => 503
    ]);
}
exit;


/**
 * Helper to perform HTTP request via cURL or native PHP streams
 */
function forwardRequest(string $method, string $url, ?string $postData = null, int $timeout = 60, array $customHeaders = []): array
{
    if (function_exists('curl_init')) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);

        $headers = array_merge([
            'Accept: application/json',
            'User-Agent: SurfacesTiles-Proxy/2.0'
        ], $customHeaders);

        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
            if ($postData !== null && !hasHeader($headers, 'Content-Length')) {
                $headers[] = 'Content-Length: ' . strlen((string)$postData);
            }
        }

        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $result = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curlError = curl_error($ch);
        curl_close($ch);

        if ($result !== false && $httpCode >= 200 && $httpCode < 500) {
            return [
                'success' => true,
                'status_code' => $httpCode,
                'body' => $result,
                'error' => null
            ];
        }

        return [
            'success' => false,
            'status_code' => $httpCode ?: 500,
            'body' => null,
            'error' => $curlError ?: "HTTP status $httpCode"
        ];
    }

    // Fallback: PHP streams
    $headers = array_merge([
        'Accept: application/json',
        'User-Agent: SurfacesTiles-Proxy/2.0'
    ], $customHeaders);

    $headerStr = implode("\r\n", $headers) . "\r\n";
    if ($method === 'POST' && $postData !== null) {
        $headerStr .= "Content-Length: " . strlen($postData) . "\r\n";
    }

    $httpOptions = [
        'method' => $method,
        'timeout' => $timeout,
        'ignore_errors' => true,
        'header' => $headerStr
    ];

    if ($method === 'POST' && $postData !== null) {
        $httpOptions['content'] = $postData;
    }

    $context = stream_context_create(['http' => $httpOptions]);
    $fp = @fopen($url, 'r', false, $context);

    if ($fp === false) {
        $lastError = error_get_last();
        return [
            'success' => false,
            'status_code' => 503,
            'body' => null,
            'error' => $lastError['message'] ?? 'Could not connect to backend server'
        ];
    }

    $responseBody = stream_get_contents($fp);
    $meta = stream_get_meta_data($fp);
    fclose($fp);

    $statusCode = 200;
    if (isset($meta['wrapper_data']) && is_array($meta['wrapper_data'])) {
        foreach ($meta['wrapper_data'] as $headerLine) {
            if (preg_match('#HTTP/\S+\s+(\d{3})#', $headerLine, $matches)) {
                $statusCode = (int)$matches[1];
                break;
            }
        }
    }

    return [
        'success' => ($statusCode >= 200 && $statusCode < 500),
        'status_code' => $statusCode,
        'body' => $responseBody,
        'error' => ($statusCode >= 500) ? "HTTP status $statusCode" : null
    ];
}

/**
 * Forward multipart form data with uploaded files via cURL
 */
function forwardMultipart(string $url, array $postFields, int $timeout = 60): array
{
    if (!function_exists('curl_init')) {
        return [
            'success' => false,
            'status_code' => 500,
            'body' => null,
            'error' => 'cURL extension required for multipart file uploads'
        ];
    }

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $postFields);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Accept: application/json',
        'User-Agent: SurfacesTiles-Proxy/2.0'
    ]);

    $result = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlError = curl_error($ch);
    curl_close($ch);

    if ($result !== false && $httpCode >= 200 && $httpCode < 500) {
        return [
            'success' => true,
            'status_code' => $httpCode,
            'body' => $result,
            'error' => null
        ];
    }

    return [
        'success' => false,
        'status_code' => $httpCode ?: 500,
        'body' => null,
        'error' => $curlError ?: "HTTP status $httpCode"
    ];
}

function hasHeader(array $headers, string $headerName): bool
{
    $lower = strtolower($headerName) . ':';
    foreach ($headers as $h) {
        if (strpos(strtolower(trim($h)), $lower) === 0) {
            return true;
        }
    }
    return false;
}
