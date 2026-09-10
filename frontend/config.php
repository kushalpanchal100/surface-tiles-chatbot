<?php
/**
 * Surfaces Tiles UK - AI Agent Chatbot Configuration
 * 
 * Central configuration file for the modern AI Agent chatbot component.
 * Can be loaded standalone or included into an existing PHP application.
 */

// Avoid multiple declarations if included multiple times
if (!defined('SOPHIE_CHAT_CONFIG_LOADED')) {
    define('SOPHIE_CHAT_CONFIG_LOADED', true);

    return [
        // Backend API settings
        'api_url' => getenv('CHATBOT_API_URL') ?: 'http://127.0.0.1:8060',
        'chat_endpoint' => '/chat',
        'voice_chat_endpoint' => '/voice/chat',
        'voice_transcribe_endpoint' => '/voice/transcribe',
        'voice_synthesize_endpoint' => '/voice/synthesize',
        'health_endpoint' => '/health',
        'api_proxy_url' => 'api-proxy.php',
        'request_timeout' => 60, // seconds (extended for voice processing on CPU)

        // Bot Branding & Identity
        'bot_name' => 'Sophie',
        'bot_status' => 'Online',
        'bot_avatar_alt' => 'Sophie - Surfaces Tiles Assistant',
        'brand_name' => 'Surfaces Tiles UK',
        'brand_url' => 'https://surfacestiles.co.uk',

        // Initial Structured Card (matches reference design)
        'initial_card' => [
            'type' => 'personal_info',
            'title' => 'Personal information',
            'subtitle' => 'The information provided below will reflect on your invoices',
            'items' => [
                ['label' => 'Name', 'value' => 'Name Surname', 'field' => 'name'],
                ['label' => 'Address', 'value' => '99 Street, City, Country', 'field' => 'address'],
                ['label' => 'Phone number', 'value' => '+1 123456789', 'field' => 'phone'],
                ['label' => 'Company', 'value' => 'Company name', 'field' => 'company'],
            ],
            'note' => 'Changes apply to **future invoices only**; invoices that have already been issued cannot be modified.',
            'timestamp' => '12:02',
        ],

        // Quick Action Capsules (matches reference design)
        'quick_actions' => [
            'How can I download my previous invoices?',
            'Where can I see my payment history?',
            'Can I update my billing address?',
            'How can I order free tile samples?',
        ],

        // Available AI Skills
        'skills' => [
            [
                'id' => 'tile_spec',
                'title' => 'Tile Specialist',
                'description' => 'Slip resistance (R-ratings), porcelain vs ceramic & underfloor heating advice.',
                'icon' => '🧱',
                'prompt' => 'Tell me about non-slip floor tiles suitable for underfloor heating',
            ],
            [
                'id' => 'calculator',
                'title' => 'Area & Box Calculator',
                'description' => 'Calculate square meters (m²), box quantities and 10% cutting wastage.',
                'icon' => '📐',
                'prompt' => 'How do I calculate tile m² quantities with 10% wastage?',
            ],
            [
                'id' => 'billing',
                'title' => 'Invoicing & Account Info',
                'description' => 'Manage billing address, previous VAT invoices and payment receipts.',
                'icon' => '💳',
                'prompt' => 'Can I update my billing address and view past invoices?',
            ],
            [
                'id' => 'samples',
                'title' => 'Sample Ordering',
                'description' => 'Request free touch-and-feel sample swatches delivered to your door.',
                'icon' => '📦',
                'prompt' => 'How do I order free tile samples to my home?',
            ],
        ],

        // Agent Persona Switcher
        'agent_models' => [
            ['id' => 'agent_general', 'name' => 'Sophie', 'role' => 'Surfaces Tiles Specialist', 'badge' => 'Default'],
            ['id' => 'tile_pro', 'name' => 'Tile Consultant', 'role' => 'Material & Design Expert', 'badge' => 'Pro'],
            ['id' => 'order_support', 'name' => 'Billing & Orders', 'role' => 'Invoices & Customer Care', 'badge' => 'Support'],
        ],

        // Input settings
        'input_placeholder' => 'Chat with Sophie...',
        'disclaimer' => 'AI can make mistakes. Double-check replies.',
        'max_message_length' => 1000,

        // Help Modal Content
        'help' => [
            'title' => 'How can Sophie help you?',
            'description' => 'Your AI specialist for Surfaces Tiles UK. Here are things you can ask:',
            'topics' => [
                'Tile recommendations for kitchens, bathrooms, floors, and outdoor patios.',
                'Technical specifications: R-ratings, slip resistance, porcelain vs ceramic, and underfloor heating suitability.',
                'Tile calculations and square meter (m²) quantity guidance.',
                'Order samples, check delivery policies, returns, and showroom details.',
                'Invoices, account updates, and showroom appointments.'
            ],
            'contact_phone' => '020 8452 4688',
            'contact_email' => 'sales@surfacestiles.co.uk'
        ],

        // Display mode: 'floating' (docked widget at bottom-right) or 'card' (embedded in footer/page)
        'default_mode' => 'floating',
    ];
}
