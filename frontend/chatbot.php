<?php
/**
 * Surfaces Tiles UK - Modern AI Agent Chatbot Component
 * 
 * Embeddable, self-contained PHP widget matching the modern Agent reference design.
 * 
 * Usage in any website template or footer:
 * <?php include __DIR__ . '/path/to/frontend/chatbot.php'; ?>
 * 
 * Optional configuration variables before include:
 * - $chatbot_mode = 'floating'; // 'floating' (default bottom-right) or 'card' (embedded inline)
 * - $chatbot_assets_url = 'assets'; // Path to assets directory
 * - $chatbot_api_url = 'api-proxy.php'; // Path to proxy endpoint
 */

// Load configuration
$sophieConfig = require __DIR__ . '/config.php';

// Allow runtime overrides (via GET parameter or pre-set variable)
$widgetMode = $_GET['mode'] ?? ($chatbot_mode ?? ($sophieConfig['default_mode'] ?? 'floating'));
$assetsUrl = isset($chatbot_assets_url) ? rtrim($chatbot_assets_url, '/') : 'assets';
$proxyUrl = isset($chatbot_api_url) ? $chatbot_api_url : ($sophieConfig['api_proxy_url'] ?? 'api-proxy.php');
$cardData = $sophieConfig['initial_card'] ?? null;
?>

<!-- =========================================================================
     MODERN AI AGENT CHATBOT COMPONENT (Surfaces Tiles UK)
     Scoped markup - matches reference design
     ========================================================================= -->

<!-- Scoped CSS -->
<link rel="stylesheet" href="<?php echo htmlspecialchars($assetsUrl); ?>/css/sophie-chat.css">

<!-- Floating Launcher Trigger Button (used in floating mode) -->
<div id="sophie-chat-launcher" style="<?php echo ($widgetMode === 'card' || $widgetMode === 'inline') ? 'display: none;' : ''; ?>">
    <div class="sophie-launcher-badge" id="sophie-launcher-badge">
        <span class="sophie-launcher-badge-dot"></span>
        <span>Chat with <?php echo htmlspecialchars($sophieConfig['bot_name']); ?></span>
    </div>
    <button type="button" class="sophie-launcher-btn" id="sophie-launcher-toggle" aria-label="Toggle Surfaces Tiles Chatbot">
        <!-- Open Icon: Modern Origami Agent Star -->
        <span class="sophie-launcher-icon-open">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
                <path d="M16 2L19.5 12.5L30 16L19.5 19.5L16 30L12.5 19.5L2 16L12.5 12.5L16 2Z" fill="url(#launcher-origami-grad)"/>
                <path d="M16 2L19.5 12.5L16 16L12.5 12.5L16 2Z" fill="#A78BFA" fill-opacity="0.9"/>
                <path d="M30 16L19.5 19.5L16 16L19.5 12.5L30 16Z" fill="#7C3AED"/>
                <path d="M16 30L12.5 19.5L16 16L19.5 19.5L16 30Z" fill="#6366F1"/>
                <path d="M2 16L12.5 12.5L16 16L12.5 19.5L2 16Z" fill="#8B5CF6"/>
                <defs>
                    <linearGradient id="launcher-origami-grad" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#8B5CF6"/>
                        <stop offset="0.5" stop-color="#7C3AED"/>
                        <stop offset="1" stop-color="#6366F1"/>
                    </linearGradient>
                </defs>
            </svg>
        </span>
        <!-- Close Icon: Cross -->
        <span class="sophie-launcher-icon-close">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </span>
    </button>
</div>

<!-- Main Agent Chat Widget Container -->
<div id="sophie-chat-widget" data-mode="<?php echo htmlspecialchars($widgetMode); ?>" class="<?php echo ($widgetMode === 'card' || $widgetMode === 'inline') ? 'sophie-mode-inline is-visible' : ''; ?>">
    
    <!-- 1. Header Bar -->
    <div class="sophie-header">
        <div class="sophie-header-left">
            <!-- Menu / Hamburger Button -->
            <button type="button" class="sophie-header-btn" id="sophie-menu-btn" title="Menu" aria-label="Menu">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="4" y1="6" x2="20" y2="6"></line>
                    <line x1="4" y1="12" x2="20" y2="12"></line>
                    <line x1="4" y1="18" x2="20" y2="18"></line>
                </svg>
            </button>

            <!-- Purple Folded Origami Star Logo -->
            <div class="sophie-origami-logo" aria-hidden="true">
                <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
                    <!-- 4 Faceted Wings -->
                    <path d="M16 3L19.5 12.5L16 16L12.5 12.5L16 3Z" fill="#A78BFA"/>
                    <path d="M29 16L19.5 19.5L16 16L19.5 12.5L29 16Z" fill="#7C3AED"/>
                    <path d="M16 29L12.5 19.5L16 16L19.5 19.5L16 29Z" fill="#6366F1"/>
                    <path d="M3 16L12.5 12.5L16 16L12.5 19.5L3 16Z" fill="#8B5CF6"/>
                    <circle cx="16" cy="16" r="1.5" fill="#FFFFFF"/>
                </svg>
            </div>

            <!-- Header Title -->
            <span class="sophie-header-title"><?php echo htmlspecialchars($sophieConfig['bot_name']); ?></span>
        </div>
        
        <!-- Header Actions: New Chat, Expand/Fullscreen, Close -->
        <div class="sophie-header-actions">
            <!-- New Conversation (Pencil / Compose) -->
            <button type="button" class="sophie-header-btn" id="sophie-new-chat-btn" title="New conversation" aria-label="New conversation">
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
            </button>

            <!-- Expand / Maximize (Two diagonal arrows) -->
            <button type="button" class="sophie-header-btn" id="sophie-expand-btn" title="Expand view" aria-label="Expand view">
                <svg class="sophie-icon-expand" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <polyline points="9 21 3 21 3 15"></polyline>
                    <line x1="21" y1="3" x2="14" y2="10"></line>
                    <line x1="3" y1="21" x2="10" y2="14"></line>
                </svg>
                <svg class="sophie-icon-collapse" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="display: none;">
                    <polyline points="4 14 10 14 10 20"></polyline>
                    <polyline points="20 10 14 10 14 4"></polyline>
                    <line x1="14" y1="10" x2="21" y2="3"></line>
                    <line x1="3" y1="21" x2="10" y2="14"></line>
                </svg>
            </button>
            
            <!-- Close (✕) Button -->
            <button type="button" class="sophie-header-btn" id="sophie-close-btn" title="Close" aria-label="Close">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    </div>

    <!-- Quick Navigation / Menu Dropdown Drawer -->
    <div class="sophie-menu-drawer" id="sophie-menu-drawer">
        <div class="sophie-menu-drawer-header">
            <span>Quick Menu</span>
            <button type="button" class="sophie-menu-close-btn" id="sophie-menu-close-btn">&times;</button>
        </div>
        <div class="sophie-menu-items">
            <button type="button" class="sophie-menu-item" data-action="new-chat">
                <span class="sophie-menu-icon">📝</span>
                <span class="sophie-menu-text">Start New Conversation</span>
            </button>
            <button type="button" class="sophie-menu-item" data-action="help">
                <span class="sophie-menu-icon">❓</span>
                <span class="sophie-menu-text">Specialist Capabilities & Help</span>
            </button>
            <button type="button" class="sophie-menu-item" data-action="query" data-query="Show me showroom opening hours and address in London">
                <span class="sophie-menu-icon">📍</span>
                <span class="sophie-menu-text">Showroom Location & Hours</span>
            </button>
            <button type="button" class="sophie-menu-item" data-action="query" data-query="How can I order tile samples?">
                <span class="sophie-menu-icon">📦</span>
                <span class="sophie-menu-text">Order Free Tile Samples</span>
            </button>
            <button type="button" class="sophie-menu-item" data-action="query" data-query="Can I speak to customer service?">
                <span class="sophie-menu-icon">📞</span>
                <span class="sophie-menu-text">Contact Specialist Team</span>
            </button>
        </div>
    </div>

    <!-- 2. Scrollable Body / Messages -->
    <div class="sophie-body" id="sophie-chat-body">
        
        <!-- Welcome Block with Structured Card -->
        <div class="sophie-welcome-container" id="sophie-welcome-container">
            <?php if ($cardData): ?>
            <!-- Structured Data Card (Matches Reference Screenshot) -->
            <div class="sophie-card-wrapper">
                <div class="sophie-card">
                    <!-- Card Header -->
                    <div class="sophie-card-head">
                        <div class="sophie-card-head-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M20 4H4C2.89 4 2.01 4.89 2.01 6L2 18C2 19.11 2.89 20 4 20H20C21.11 20 22 19.11 22 18V6C22 4.89 21.11 4 20 4ZM20 18H4V6H20V18ZM6 10H10V12H6V10ZM6 14H10V16H6V14ZM12 8H18V10H12V8ZM12 12H18V14H12V12ZM12 16H18V18H12V16Z"/>
                            </svg>
                        </div>
                        <div class="sophie-card-head-title"><?php echo htmlspecialchars($cardData['title']); ?></div>
                    </div>

                    <!-- Subtitle / Notice -->
                    <div class="sophie-card-subtitle">
                        <?php echo htmlspecialchars($cardData['subtitle']); ?>
                    </div>

                    <!-- Card Rows (Name, Address, Phone number, Company) with Chevrons -->
                    <div class="sophie-card-rows">
                        <?php foreach ($cardData['items'] as $item): ?>
                            <div class="sophie-card-row" data-field="<?php echo htmlspecialchars($item['field']); ?>">
                                <span class="sophie-card-row-label"><?php echo htmlspecialchars($item['label']); ?></span>
                                <div class="sophie-card-row-val-group">
                                    <span class="sophie-card-row-val"><?php echo htmlspecialchars($item['value']); ?></span>
                                    <button type="button" class="sophie-card-chevron-btn" title="View or edit <?php echo htmlspecialchars($item['label']); ?>" aria-label="Open <?php echo htmlspecialchars($item['label']); ?>">
                                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                            <polyline points="9 18 15 12 9 6"></polyline>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- Follow-up Note Text -->
                <div class="sophie-card-note">
                    Changes apply to <strong>future invoices only</strong>; invoices that have already been issued cannot be modified.
                </div>

                <!-- Message Action Toolbar (Copy, Speaker/TTS, Thumbs up, Thumbs down, Time) -->
                <div class="sophie-msg-actions">
                    <button type="button" class="sophie-action-btn sophie-copy-btn" title="Copy text" aria-label="Copy">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </button>
                    <button type="button" class="sophie-action-btn sophie-tts-btn" title="Read aloud" aria-label="Read aloud">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                        </svg>
                    </button>
                    <button type="button" class="sophie-action-btn sophie-thumb-up" title="Helpful" aria-label="Helpful">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                        </svg>
                    </button>
                    <button type="button" class="sophie-action-btn sophie-thumb-down" title="Not helpful" aria-label="Not helpful">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                        </svg>
                    </button>
                    <span class="sophie-msg-time"><?php echo htmlspecialchars($cardData['timestamp'] ?? '12:02'); ?></span>
                </div>
            </div>
            <?php endif; ?>

            <!-- Quick Actions Section -->
            <div class="sophie-quick-actions-section">
                <div class="sophie-quick-actions-title">Quick actions</div>
                <div class="sophie-quick-actions-list">
                    <?php foreach ($sophieConfig['quick_actions'] as $qa): ?>
                        <button type="button" class="sophie-quick-action-pill" data-query="<?php echo htmlspecialchars($qa); ?>">
                            <span class="sophie-quick-action-text"><?php echo htmlspecialchars($qa); ?></span>
                            <span class="sophie-quick-action-chevron">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="9 18 15 12 9 6"></polyline>
                                </svg>
                            </span>
                        </button>
                    <?php endforeach; ?>
                </div>
            </div>
        </div>

        <!-- Dynamic Chat Messages will be appended here -->
        <div id="sophie-messages-stream"></div>

    </div>

    <!-- 3. Bottom Footer & Floating Input Area -->
    <div class="sophie-footer">
        
        <!-- Attached file badge (if user selected an attachment) -->
        <div class="sophie-attachment-preview" id="sophie-attachment-preview" style="display: none;">
            <span class="sophie-attach-file-icon">📎</span>
            <span class="sophie-attach-file-name" id="sophie-attach-file-name">file.pdf</span>
            <button type="button" class="sophie-attach-remove-btn" id="sophie-attach-remove-btn">&times;</button>
        </div>

        <form id="sophie-chat-form" class="sophie-chat-form">
            <!-- Text Input Container -->
            <div class="sophie-input-wrapper">
                <textarea 
                    class="sophie-input" 
                    id="sophie-chat-input" 
                    placeholder="<?php echo htmlspecialchars($sophieConfig['input_placeholder']); ?>" 
                    rows="1"
                    maxlength="<?php echo (int)$sophieConfig['max_message_length']; ?>"
                    aria-label="Chat with <?php echo htmlspecialchars($sophieConfig['bot_name']); ?>"
                ></textarea>
            </div>

            <!-- Bottom Action Row: Attachment, Skills, Agent Model Switcher, Mic Voice Button -->
            <div class="sophie-input-bottom-bar">
                
                <!-- Left Actions: Attachment & Skills -->
                <div class="sophie-bottom-left">
                    <!-- Paperclip / Attachment Button -->
                    <button type="button" class="sophie-tool-btn" id="sophie-attach-btn" title="Attach image or document" aria-label="Attach file">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                        </svg>
                    </button>
                    <input type="file" id="sophie-file-input" style="display: none;" accept="image/*,.pdf,.doc,.docx,.txt">

                    <!-- "⚡ Skills" Pill Button -->
                    <div class="sophie-skills-container">
                        <button type="button" class="sophie-skills-pill-btn" id="sophie-skills-btn" aria-expanded="false" title="View Assistant Skills">
                            <span class="sophie-skills-lightning">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                                </svg>
                            </span>
                            <span>Skills</span>
                        </button>

                        <!-- Skills Popover Menu -->
                        <div class="sophie-skills-popover" id="sophie-skills-popover">
                            <div class="sophie-popover-title">Available Capabilities</div>
                            <div class="sophie-skills-list">
                                <?php foreach ($sophieConfig['skills'] as $skill): ?>
                                    <div class="sophie-skill-item" data-prompt="<?php echo htmlspecialchars($skill['prompt']); ?>">
                                        <div class="sophie-skill-icon"><?php echo htmlspecialchars($skill['icon']); ?></div>
                                        <div class="sophie-skill-content">
                                            <div class="sophie-skill-name"><?php echo htmlspecialchars($skill['title']); ?></div>
                                            <div class="sophie-skill-desc"><?php echo htmlspecialchars($skill['description']); ?></div>
                                        </div>
                                    </div>
                                <?php endforeach; ?>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Actions: Agent Selector & Glowing Voice Button -->
                <div class="sophie-bottom-right">
                    
                    <!-- Origami Agent Switcher Dropdown Trigger -->
                    <div class="sophie-agent-select-wrapper">
                        <button type="button" class="sophie-agent-select-btn" id="sophie-agent-select-btn" aria-expanded="false">
                            <span class="sophie-mini-star">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                                    <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="#7C3AED"/>
                                </svg>
                            </span>
                            <span class="sophie-selected-agent-name" id="sophie-selected-agent-name"><?php echo htmlspecialchars($sophieConfig['bot_name']); ?></span>
                            <svg class="sophie-chevron-down" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>

                        <!-- Agent Switcher Popover -->
                        <div class="sophie-agent-dropdown" id="sophie-agent-dropdown">
                            <div class="sophie-popover-title">Select Assistant Persona</div>
                            <?php foreach ($sophieConfig['agent_models'] as $agent): ?>
                                <button type="button" class="sophie-agent-option" data-id="<?php echo htmlspecialchars($agent['id']); ?>" data-name="<?php echo htmlspecialchars($agent['name']); ?>">
                                    <div>
                                        <div class="sophie-agent-opt-name"><?php echo htmlspecialchars($agent['name']); ?></div>
                                        <div class="sophie-agent-opt-role"><?php echo htmlspecialchars($agent['role']); ?></div>
                                    </div>
                                    <span class="sophie-agent-opt-badge"><?php echo htmlspecialchars($agent['badge']); ?></span>
                                </button>
                            <?php endforeach; ?>
                        </div>
                    </div>

                    <!-- Send Button (appears when input has text) -->
                    <button type="submit" class="sophie-send-btn" id="sophie-chat-send-btn" title="Send message" aria-label="Send message" style="display: none;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.01 21L23 12L2.01 3L2 10L17 12L2 14L2.01 21Z"/>
                        </svg>
                    </button>

                    <!-- Circular Voice Microphone Button with Gradient Ring -->
                    <button type="button" class="sophie-voice-btn" id="sophie-voice-btn" title="Click to speak (Voice input)" aria-label="Voice input">
                        <span class="sophie-voice-ring"></span>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </button>

                </div>

            </div>
        </form>

        <!-- Bottom Disclaimer -->
        <div class="sophie-disclaimer">
            <?php echo htmlspecialchars($sophieConfig['disclaimer']); ?>
        </div>
    </div>

</div>

<!-- 4. Help & Guidance Modal -->
<div class="sophie-help-modal" id="sophie-help-modal">
    <div class="sophie-help-card">
        <div class="sophie-help-title">
            <div class="sophie-origami-logo" style="width:28px; height:28px;">
                <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
                    <path d="M16 3L19.5 12.5L16 16L12.5 12.5L16 3Z" fill="#A78BFA"/>
                    <path d="M29 16L19.5 19.5L16 16L19.5 12.5L29 16Z" fill="#7C3AED"/>
                    <path d="M16 29L12.5 19.5L16 16L19.5 19.5L16 29Z" fill="#6366F1"/>
                    <path d="M3 16L12.5 12.5L16 16L12.5 19.5L3 16Z" fill="#8B5CF6"/>
                </svg>
            </div>
            <span><?php echo htmlspecialchars($sophieConfig['help']['title']); ?></span>
        </div>
        <p class="sophie-help-desc"><?php echo htmlspecialchars($sophieConfig['help']['description']); ?></p>
        <ul class="sophie-help-list">
            <?php foreach ($sophieConfig['help']['topics'] as $topic): ?>
                <li><?php echo htmlspecialchars($topic); ?></li>
            <?php endforeach; ?>
        </ul>
        <div class="sophie-help-contact">
            Need showroom assistance?<br>
            📞 Phone: <strong><?php echo htmlspecialchars($sophieConfig['help']['contact_phone']); ?></strong><br>
            ✉️ Email: <strong><?php echo htmlspecialchars($sophieConfig['help']['contact_email']); ?></strong>
        </div>
        <button type="button" class="sophie-help-close-btn" id="sophie-help-close-btn">Close</button>
    </div>
</div>

<!-- Toast Notification Container -->
<div class="sophie-toast" id="sophie-toast"></div>

<!-- Pass runtime config to JavaScript -->
<script>
window.SOPHIE_CHAT_CONFIG = {
    apiProxyUrl: <?php echo json_encode($proxyUrl); ?>,
    botName: <?php echo json_encode($sophieConfig['bot_name']); ?>,
    mode: <?php echo json_encode($widgetMode); ?>,
    initialCard: <?php echo json_encode($cardData); ?>
};
</script>
<!-- Client Script -->
<script src="<?php echo htmlspecialchars($assetsUrl); ?>/js/sophie-chat.js" defer></script>
