/**
 * Surfaces Tiles UK - AI Agent Chatbot Client Script
 * Zero-dependency modern vanilla JavaScript controller matching the reference UI.
 */

(function () {
    'use strict';

    class SophieAgentChatbot {
        constructor() {
            this.config = Object.assign({
                apiProxyUrl: 'api-proxy.php',
                botName: 'Sophie',
                mode: 'floating', // 'floating' or 'card'
                storagePrefix: 'sophie_agent_',
                autoScroll: true
            }, window.SOPHIE_CHAT_CONFIG || {});

            this.elements = {};
            this.isOpen = false;
            this.isExpanded = false;
            this.isSubmitting = false;
            this.isRecording = false;
            this.isProcessingVoice = false;
            this.mediaRecorder = null;
            this.mediaStream = null;
            this.audioChunks = [];
            this.currentAudio = null;
            this.activeAudioRow = null;
            this.currentUtterance = null;
            this.attachedFile = null;

            this.sessionId = this.getOrCreateSessionId();
            this.conversationHistory = [];

            this.init();
        }

        init() {
            this.bindElements();
            if (!this.elements.widget) {
                console.warn('[AgentChat] Widget container not found in DOM.');
                return;
            }

            this.initVoiceAssistant();
            this.attachEventListeners();
            this.applyInitialMode();
        }

        bindElements() {
            this.elements = {
                widget: document.getElementById('sophie-chat-widget'),
                launcher: document.getElementById('sophie-chat-launcher'),
                launcherBtn: document.getElementById('sophie-launcher-toggle'),
                launcherBadge: document.getElementById('sophie-launcher-badge'),
                headerTitle: document.querySelector('.sophie-header-title'),
                menuBtn: document.getElementById('sophie-menu-btn'),
                menuDrawer: document.getElementById('sophie-menu-drawer'),
                menuCloseBtn: document.getElementById('sophie-menu-close-btn'),
                newChatBtn: document.getElementById('sophie-new-chat-btn'),
                expandBtn: document.getElementById('sophie-expand-btn'),
                closeBtn: document.getElementById('sophie-close-btn'),
                helpModal: document.getElementById('sophie-help-modal'),
                helpCloseBtn: document.getElementById('sophie-help-close-btn'),
                body: document.getElementById('sophie-chat-body'),
                welcomeContainer: document.getElementById('sophie-welcome-container'),
                messagesStream: document.getElementById('sophie-messages-stream'),
                form: document.getElementById('sophie-chat-form'),
                input: document.getElementById('sophie-chat-input'),
                sendBtn: document.getElementById('sophie-chat-send-btn'),
                voiceBtn: document.getElementById('sophie-voice-btn'),
                attachBtn: document.getElementById('sophie-attach-btn'),
                fileInput: document.getElementById('sophie-file-input'),
                attachPreview: document.getElementById('sophie-attachment-preview'),
                attachFileName: document.getElementById('sophie-attach-file-name'),
                attachRemoveBtn: document.getElementById('sophie-attach-remove-btn'),
                skillsBtn: document.getElementById('sophie-skills-btn'),
                skillsPopover: document.getElementById('sophie-skills-popover'),
                agentSelectBtn: document.getElementById('sophie-agent-select-btn'),
                agentDropdown: document.getElementById('sophie-agent-dropdown'),
                selectedAgentName: document.getElementById('sophie-selected-agent-name'),
                toast: document.getElementById('sophie-toast')
            };
        }

        attachEventListeners() {
            // Launcher toggles
            if (this.elements.launcherBtn) {
                this.elements.launcherBtn.addEventListener('click', () => this.toggle());
            }
            if (this.elements.launcherBadge) {
                this.elements.launcherBadge.addEventListener('click', () => this.open());
            }

            // Header actions
            if (this.elements.closeBtn) {
                this.elements.closeBtn.addEventListener('click', () => this.close());
            }
            if (this.elements.expandBtn) {
                this.elements.expandBtn.addEventListener('click', () => this.toggleExpand());
            }
            if (this.elements.newChatBtn) {
                this.elements.newChatBtn.addEventListener('click', () => this.resetConversation());
            }
            if (this.elements.menuBtn) {
                this.elements.menuBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleMenuDrawer();
                });
            }
            if (this.elements.menuCloseBtn) {
                this.elements.menuCloseBtn.addEventListener('click', () => this.closeMenuDrawer());
            }

            // Menu Drawer item clicks
            if (this.elements.menuDrawer) {
                const menuItems = this.elements.menuDrawer.querySelectorAll('.sophie-menu-item');
                menuItems.forEach((btn) => {
                    btn.addEventListener('click', (e) => {
                        const action = e.currentTarget.getAttribute('data-action');
                        this.closeMenuDrawer();
                        if (action === 'new-chat') {
                            this.resetConversation();
                        } else if (action === 'help') {
                            this.openHelp();
                        } else if (action === 'query') {
                            const query = e.currentTarget.getAttribute('data-query');
                            if (query) this.sendMessage(query);
                        }
                    });
                });
            }

            // Help Modal
            if (this.elements.helpCloseBtn) {
                this.elements.helpCloseBtn.addEventListener('click', () => this.closeHelp());
            }
            if (this.elements.helpModal) {
                this.elements.helpModal.addEventListener('click', (e) => {
                    if (e.target === this.elements.helpModal) this.closeHelp();
                });
            }

            // Quick Actions Pills
            const pills = document.querySelectorAll('.sophie-quick-action-pill');
            pills.forEach((pill) => {
                pill.addEventListener('click', (e) => {
                    const query = e.currentTarget.getAttribute('data-query') || e.currentTarget.textContent.trim();
                    this.sendMessage(query);
                });
            });

            // Card row chevron clicks (e.g. Name, Address, Phone, Company)
            this.bindCardRowClicks();

            // Initial Welcome Card message actions (Copy, TTS, Thumbs)
            const initialActionRow = document.querySelector('.sophie-card-wrapper .sophie-msg-actions');
            if (initialActionRow) {
                this.bindMessageActionEvents(initialActionRow, "Changes apply to future invoices only; invoices that have already been issued cannot be modified.");
            }

            // Skills Popover Toggle
            if (this.elements.skillsBtn && this.elements.skillsPopover) {
                this.elements.skillsBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.closeAllPopovers(this.elements.skillsPopover);
                    this.elements.skillsPopover.classList.toggle('is-active');
                    this.elements.skillsBtn.setAttribute('aria-expanded', this.elements.skillsPopover.classList.contains('is-active'));
                });

                const skillItems = this.elements.skillsPopover.querySelectorAll('.sophie-skill-item');
                skillItems.forEach((item) => {
                    item.addEventListener('click', (e) => {
                        const prompt = e.currentTarget.getAttribute('data-prompt');
                        this.elements.skillsPopover.classList.remove('is-active');
                        if (prompt) this.sendMessage(prompt);
                    });
                });
            }

            // Agent Switcher Dropdown
            if (this.elements.agentSelectBtn && this.elements.agentDropdown) {
                this.elements.agentSelectBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.closeAllPopovers(this.elements.agentDropdown);
                    this.elements.agentDropdown.classList.toggle('is-active');
                    this.elements.agentSelectBtn.setAttribute('aria-expanded', this.elements.agentDropdown.classList.contains('is-active'));
                });

                const agentOptions = this.elements.agentDropdown.querySelectorAll('.sophie-agent-option');
                agentOptions.forEach((opt) => {
                    opt.addEventListener('click', (e) => {
                        const name = e.currentTarget.getAttribute('data-name');
                        if (this.elements.selectedAgentName) {
                            this.elements.selectedAgentName.textContent = name;
                        }
                        this.elements.agentDropdown.classList.remove('is-active');
                        this.showToast(`Switched persona to ${name}`);
                    });
                });
            }

            // Close popovers on outside click
            document.addEventListener('click', (e) => {
                if (this.elements.skillsPopover && !this.elements.skillsPopover.contains(e.target) && e.target !== this.elements.skillsBtn) {
                    this.elements.skillsPopover.classList.remove('is-active');
                }
                if (this.elements.agentDropdown && !this.elements.agentDropdown.contains(e.target) && e.target !== this.elements.agentSelectBtn) {
                    this.elements.agentDropdown.classList.remove('is-active');
                }
                if (this.elements.menuDrawer && !this.elements.menuDrawer.contains(e.target) && e.target !== this.elements.menuBtn) {
                    this.closeMenuDrawer();
                }
            });

            // Attachment Handling
            if (this.elements.attachBtn && this.elements.fileInput) {
                this.elements.attachBtn.addEventListener('click', () => {
                    this.elements.fileInput.click();
                });

                this.elements.fileInput.addEventListener('change', (e) => {
                    if (e.target.files && e.target.files[0]) {
                        this.attachedFile = e.target.files[0];
                        if (this.elements.attachFileName) {
                            this.elements.attachFileName.textContent = this.attachedFile.name;
                        }
                        if (this.elements.attachPreview) {
                            this.elements.attachPreview.style.display = 'flex';
                        }
                        this.showToast(`Attached ${this.attachedFile.name}`);
                    }
                });
            }

            if (this.elements.attachRemoveBtn) {
                this.elements.attachRemoveBtn.addEventListener('click', () => {
                    this.attachedFile = null;
                    if (this.elements.fileInput) this.elements.fileInput.value = '';
                    if (this.elements.attachPreview) this.elements.attachPreview.style.display = 'none';
                });
            }

            // Voice Button (Speech-to-Text)
            if (this.elements.voiceBtn) {
                this.elements.voiceBtn.addEventListener('click', () => this.toggleVoiceInput());
            }

            // Input interactions (auto-expand, send button display, enter submit)
            if (this.elements.input) {
                this.elements.input.addEventListener('input', () => {
                    this.adjustInputHeight();
                    const hasText = this.elements.input.value.trim().length > 0;
                    if (this.elements.sendBtn) {
                        this.elements.sendBtn.style.display = hasText ? 'flex' : 'none';
                    }
                });

                this.elements.input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.handleUserSubmit();
                    }
                });
            }

            // Form Submit
            if (this.elements.form) {
                this.elements.form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.handleUserSubmit();
                });
            }
        }

        bindCardRowClicks() {
            const rows = document.querySelectorAll('.sophie-card-row');
            rows.forEach((row) => {
                const chevronBtn = row.querySelector('.sophie-card-chevron-btn');
                const field = row.getAttribute('data-field') || '';
                const label = row.querySelector('.sophie-card-row-label')?.textContent.trim() || field;
                const value = row.querySelector('.sophie-card-row-val')?.textContent.trim() || '';

                const triggerAction = () => {
                    let prompt = '';
                    if (field === 'company') {
                        prompt = `How can I update my company name for invoices?`;
                    } else if (field === 'address') {
                        prompt = `Can I update my billing address for future invoices?`;
                    } else if (field === 'phone') {
                        prompt = `How do I change the phone number linked to my account?`;
                    } else if (field === 'name') {
                        prompt = `How can I update my name on my invoices?`;
                    } else {
                        prompt = `Can I modify my ${label}?`;
                    }
                    this.sendMessage(prompt);
                };

                if (chevronBtn) {
                    chevronBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        triggerAction();
                    });
                }
                row.addEventListener('click', () => {
                    triggerAction();
                });
            });
        }

        closeAllPopovers(exceptElement) {
            if (this.elements.skillsPopover && this.elements.skillsPopover !== exceptElement) {
                this.elements.skillsPopover.classList.remove('is-active');
            }
            if (this.elements.agentDropdown && this.elements.agentDropdown !== exceptElement) {
                this.elements.agentDropdown.classList.remove('is-active');
            }
            if (this.elements.menuDrawer && this.elements.menuDrawer !== exceptElement) {
                this.closeMenuDrawer();
            }
        }

        toggleMenuDrawer() {
            if (this.elements.menuDrawer) {
                this.elements.menuDrawer.classList.toggle('is-active');
            }
        }

        closeMenuDrawer() {
            if (this.elements.menuDrawer) {
                this.elements.menuDrawer.classList.remove('is-active');
            }
        }

        applyInitialMode() {
            const containerMode = this.elements.widget.getAttribute('data-mode') || this.config.mode;
            if (containerMode === 'card' || containerMode === 'inline') {
                this.elements.widget.classList.add('sophie-mode-inline');
                if (this.elements.launcher) {
                    this.elements.launcher.style.display = 'none';
                }
                this.isOpen = true;
            } else {
                this.elements.widget.classList.remove('sophie-mode-inline');
                if (this.elements.launcher) {
                    this.elements.launcher.style.display = 'flex';
                }
            }
        }

        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }

        open() {
            if (this.elements.widget.classList.contains('sophie-mode-inline')) return;
            this.isOpen = true;
            this.elements.widget.classList.add('is-visible');
            if (this.elements.launcher) {
                this.elements.launcher.classList.add('is-open');
            }
            if (this.elements.input) {
                setTimeout(() => this.elements.input.focus(), 220);
            }
            this.scrollToBottom();
        }

        close() {
            if (this.elements.widget.classList.contains('sophie-mode-inline')) return;
            this.isOpen = false;
            this.elements.widget.classList.remove('is-visible');
            if (this.elements.launcher) {
                this.elements.launcher.classList.remove('is-open');
            }
            this.stopSpeaking();
            this.stopRecording();
        }

        toggleExpand() {
            this.isExpanded = !this.isExpanded;
            this.elements.widget.classList.toggle('is-expanded', this.isExpanded);

            const expandIcon = this.elements.expandBtn?.querySelector('.sophie-icon-expand');
            const collapseIcon = this.elements.expandBtn?.querySelector('.sophie-icon-collapse');

            if (expandIcon && collapseIcon) {
                expandIcon.style.display = this.isExpanded ? 'none' : 'block';
                collapseIcon.style.display = this.isExpanded ? 'block' : 'none';
            }
            this.scrollToBottom();
        }

        openHelp() {
            if (this.elements.helpModal) {
                this.elements.helpModal.classList.add('is-active');
            }
        }

        closeHelp() {
            if (this.elements.helpModal) {
                this.elements.helpModal.classList.remove('is-active');
            }
        }

        resetConversation() {
            this.stopSpeaking();
            this.stopRecording();
            this.conversationHistory = [];
            this.sessionId = this.generateUuid();

            if (this.elements.messagesStream) {
                this.elements.messagesStream.innerHTML = '';
            }
            if (this.elements.welcomeContainer) {
                this.elements.welcomeContainer.style.display = 'flex';
            }
            if (this.elements.input) {
                this.elements.input.value = '';
                this.elements.input.style.height = 'auto';
            }
            if (this.elements.sendBtn) {
                this.elements.sendBtn.style.display = 'none';
            }

            this.showToast('New conversation started');
            this.scrollToBottom();
        }

        adjustInputHeight() {
            if (!this.elements.input) return;
            this.elements.input.style.height = 'auto';
            this.elements.input.style.height = Math.min(this.elements.input.scrollHeight, 110) + 'px';
        }

        handleUserSubmit() {
            if (this.isSubmitting || !this.elements.input) return;
            let message = this.elements.input.value.trim();
            if (!message && !this.attachedFile) return;

            if (this.attachedFile) {
                message = message ? `[Attached file: ${this.attachedFile.name}]\n${message}` : `[Attached file: ${this.attachedFile.name}]`;
                this.attachedFile = null;
                if (this.elements.fileInput) this.elements.fileInput.value = '';
                if (this.elements.attachPreview) this.elements.attachPreview.style.display = 'none';
            }

            this.elements.input.value = '';
            this.adjustInputHeight();
            if (this.elements.sendBtn) {
                this.elements.sendBtn.style.display = 'none';
            }

            this.sendMessage(message);
        }

        async sendMessage(messageText) {
            if (!messageText || this.isSubmitting) return;

            // Make sure chat window is visible
            if (!this.isOpen && !this.elements.widget.classList.contains('sophie-mode-inline')) {
                this.open();
            }

            // 1. Render User Message
            this.appendUserMessage(messageText);

            // Record to conversation history
            this.conversationHistory.push({ role: 'user', content: messageText });

            // 2. Set submitting state & show typing indicator
            this.setSubmitting(true);
            const typingIndicator = this.showTypingIndicator();

            try {
                // 3. Send request to PHP Proxy
                const response = await fetch(this.config.apiProxyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        message: messageText,
                        session_id: this.sessionId,
                        history: this.conversationHistory.slice(-8)
                    })
                });

                const data = await response.json();

                // Remove typing indicator
                typingIndicator.remove();

                if (response.ok && data.data && data.data.Response) {
                    const botReply = data.data.Response;
                    this.conversationHistory.push({ role: 'assistant', content: botReply });
                    this.appendAssistantMessage(botReply);
                } else {
                    const fallbackMsg = (data.data && data.data.Response) ||
                        "I'm temporarily having trouble connecting to Surfaces Tiles. Please call our London showroom at 020 8452 4688 or try again shortly.";
                    this.appendAssistantMessage(fallbackMsg);
                }
            } catch (err) {
                console.error('[AgentChat] Network/Fetch error:', err);
                typingIndicator.remove();
                this.appendAssistantMessage(
                    "I'm currently unable to reach the server. Please check your connection or browse our collections at [surfacestiles.co.uk](https://surfacestiles.co.uk)."
                );
            } finally {
                this.setSubmitting(false);
                this.scrollToBottom();
                if (this.elements.input) {
                    this.elements.input.focus();
                }
            }
        }

        appendUserMessage(text) {
            const row = document.createElement('div');
            row.className = 'sophie-msg-row sophie-msg-user';

            const bubble = document.createElement('div');
            bubble.className = 'sophie-msg-bubble';
            bubble.textContent = text;

            row.appendChild(bubble);
            this.elements.messagesStream.appendChild(row);
            this.scrollToBottom();
        }

        appendAssistantMessage(rawText, meta = {}) {
            const row = document.createElement('div');
            row.className = 'sophie-msg-row sophie-msg-assistant';

            if (meta.audioDataUri) {
                row.dataset.cachedAudio = meta.audioDataUri;
            }

            // Message Bubble
            const bubble = document.createElement('div');
            bubble.className = 'sophie-msg-bubble';

            // If generated via voice or has audio, add audio badge
            if (meta.isVoice || meta.audioDataUri) {
                const audioPill = document.createElement('div');
                audioPill.className = 'sophie-audio-pill';
                audioPill.title = 'Click to listen or pause voice response';
                audioPill.innerHTML = `
                    <span class="sophie-audio-wave">
                        <span class="sophie-audio-wave-bar"></span>
                        <span class="sophie-audio-wave-bar"></span>
                        <span class="sophie-audio-wave-bar"></span>
                    </span>
                    <span>Voice response</span>
                `;
                audioPill.addEventListener('click', () => {
                    const ttsBtn = row.querySelector('.sophie-tts-btn');
                    this.toggleSpeech(rawText, ttsBtn, row);
                });
                bubble.appendChild(audioPill);
            }

            const textDiv = document.createElement('div');
            textDiv.className = 'sophie-msg-content';
            textDiv.innerHTML = this.formatMarkdown(rawText);
            bubble.appendChild(textDiv);

            // Action Toolbar (Copy, Speaker, Thumbs, Timestamp)
            const actions = document.createElement('div');
            actions.className = 'sophie-msg-actions';
            actions.innerHTML = `
                <button type="button" class="sophie-action-btn sophie-copy-btn" title="Copy text" aria-label="Copy">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                </button>
                <button type="button" class="sophie-action-btn sophie-tts-btn" title="Read aloud (Natural Voice)" aria-label="Read aloud">
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
                <span class="sophie-msg-time">${this.getCurrentTimeString()}</span>
            `;

            this.bindMessageActionEvents(actions, rawText, row);

            row.appendChild(bubble);
            row.appendChild(actions);
            this.elements.messagesStream.appendChild(row);
            this.scrollToBottom();

            return row;
        }

        bindMessageActionEvents(actionsContainer, rawText, rowElement) {
            const copyBtn = actionsContainer.querySelector('.sophie-copy-btn');
            const ttsBtn = actionsContainer.querySelector('.sophie-tts-btn');
            const thumbUp = actionsContainer.querySelector('.sophie-thumb-up');
            const thumbDown = actionsContainer.querySelector('.sophie-thumb-down');

            if (copyBtn) {
                copyBtn.addEventListener('click', () => {
                    const cleanText = rawText.replace(/[*_#`[\]()]/g, '');
                    if (navigator.clipboard) {
                        navigator.clipboard.writeText(cleanText).then(() => {
                            this.showToast('Copied to clipboard');
                        });
                    }
                });
            }

            if (ttsBtn) {
                ttsBtn.addEventListener('click', () => {
                    this.toggleSpeech(rawText, ttsBtn, rowElement);
                });
            }

            if (thumbUp) {
                thumbUp.addEventListener('click', () => {
                    thumbUp.classList.toggle('is-active');
                    if (thumbDown) thumbDown.classList.remove('is-active');
                    if (thumbUp.classList.contains('is-active')) {
                        this.showToast('Thanks for your feedback!');
                    }
                });
            }

            if (thumbDown) {
                thumbDown.addEventListener('click', () => {
                    thumbDown.classList.toggle('is-active');
                    if (thumbUp) thumbUp.classList.remove('is-active');
                    if (thumbDown.classList.contains('is-active')) {
                        this.showToast('Thanks for your feedback!');
                    }
                });
            }
        }

        async toggleSpeech(text, btnElement, rowElement) {
            // If this message row is already playing, pause and stop it
            if (this.currentAudio && this.activeAudioRow === rowElement) {
                this.stopAnyPlayingAudio();
                return;
            }

            this.stopAnyPlayingAudio();

            // Check for cached synthesized audio on this row
            if (rowElement && rowElement.dataset.cachedAudio) {
                this.playAudioResponse(rowElement.dataset.cachedAudio, rowElement);
                return;
            }

            // Fetch synthesized audio from backend Edge-TTS
            if (btnElement) btnElement.classList.add('is-speaking');
            try {
                const synthUrl = `${this.config.apiProxyUrl}?action=synthesize`;
                const res = await fetch(synthUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });
                const data = await res.json();
                if (res.ok && data && data.audio_base64) {
                    if (rowElement) {
                        rowElement.dataset.cachedAudio = data.audio_base64;
                    }
                    this.playAudioResponse(data.audio_base64, rowElement);
                } else {
                    this.browserFallbackSpeech(text, btnElement);
                }
            } catch (err) {
                console.warn('[AgentChat] TTS service error, using fallback:', err);
                this.browserFallbackSpeech(text, btnElement);
            }
        }

        playAudioResponse(audioUri, messageRowElement) {
            this.stopAnyPlayingAudio();

            const audio = new Audio(audioUri);
            this.currentAudio = audio;
            this.activeAudioRow = messageRowElement;

            let ttsBtn = null;
            let audioPill = null;
            if (messageRowElement) {
                ttsBtn = messageRowElement.querySelector('.sophie-tts-btn');
                audioPill = messageRowElement.querySelector('.sophie-audio-pill');
                if (ttsBtn) ttsBtn.classList.add('is-speaking');
                if (audioPill) audioPill.classList.add('is-playing');
            }

            audio.onended = () => {
                if (ttsBtn) ttsBtn.classList.remove('is-speaking');
                if (audioPill) audioPill.classList.remove('is-playing');
                this.currentAudio = null;
                this.activeAudioRow = null;
            };

            audio.onerror = (e) => {
                console.warn('[AgentChat] Audio playback error:', e);
                if (ttsBtn) ttsBtn.classList.remove('is-speaking');
                if (audioPill) audioPill.classList.remove('is-playing');
                this.currentAudio = null;
                this.activeAudioRow = null;
            };

            audio.play().catch(e => {
                console.warn('[AgentChat] Audio play prevented by browser autoplay policy:', e);
                if (ttsBtn) ttsBtn.classList.remove('is-speaking');
                if (audioPill) audioPill.classList.remove('is-playing');
            });
        }

        stopAnyPlayingAudio() {
            if (this.currentAudio) {
                try {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                } catch (e) {}
                this.currentAudio = null;
            }
            if (this.activeAudioRow) {
                const ttsBtn = this.activeAudioRow.querySelector('.sophie-tts-btn');
                const audioPill = this.activeAudioRow.querySelector('.sophie-audio-pill');
                if (ttsBtn) ttsBtn.classList.remove('is-speaking');
                if (audioPill) audioPill.classList.remove('is-playing');
                this.activeAudioRow = null;
            }
            if (window.speechSynthesis && window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
            }
            document.querySelectorAll('.sophie-tts-btn.is-speaking').forEach(b => b.classList.remove('is-speaking'));
            document.querySelectorAll('.sophie-audio-pill.is-playing').forEach(p => p.classList.remove('is-playing'));
        }

        browserFallbackSpeech(text, btnElement) {
            if (!('speechSynthesis' in window)) {
                this.showToast('Speech playback not supported in this browser');
                if (btnElement) btnElement.classList.remove('is-speaking');
                return;
            }

            const cleanText = text.replace(/[*_#`[\]()]/g, '').replace(/https?:\/\/\S+/g, '');
            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.lang = 'en-GB';

            utterance.onstart = () => {
                if (btnElement) btnElement.classList.add('is-speaking');
            };
            utterance.onend = () => {
                if (btnElement) btnElement.classList.remove('is-speaking');
            };
            utterance.onerror = () => {
                if (btnElement) btnElement.classList.remove('is-speaking');
            };

            this.currentUtterance = utterance;
            window.speechSynthesis.speak(utterance);
        }

        // Voice Assistant (Speech-to-Text & Text-to-Speech)
        initVoiceAssistant() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.warn('[AgentChat] MediaDevices getUserMedia not supported in this browser.');
            }
        }

        async toggleVoiceInput() {
            if (this.isProcessingVoice) {
                this.showToast('Please wait, processing voice message...');
                return;
            }

            if (this.isRecording) {
                this.stopRecording();
            } else {
                await this.startRecording();
            }
        }

        async startRecording() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.showToast('Microphone access is not supported in this browser.');
                return;
            }

            this.stopAnyPlayingAudio();

            try {
                this.mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });

                this.audioChunks = [];
                let mimeType = 'audio/webm;codecs=opus';
                if (!window.MediaRecorder || !MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = (window.MediaRecorder && MediaRecorder.isTypeSupported('audio/webm')) ? 'audio/webm' : '';
                }

                const options = mimeType ? { mimeType } : {};
                this.mediaRecorder = new MediaRecorder(this.mediaStream, options);

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };

                this.mediaRecorder.onstart = () => {
                    this.isRecording = true;
                    if (this.elements.voiceBtn) {
                        this.elements.voiceBtn.classList.add('is-recording');
                        this.elements.voiceBtn.setAttribute('title', 'Click to finish speaking and send');
                    }
                    this.showToast('Listening... Click mic when finished speaking');
                };

                this.mediaRecorder.onstop = () => {
                    this.isRecording = false;
                    if (this.elements.voiceBtn) {
                        this.elements.voiceBtn.classList.remove('is-recording');
                        this.elements.voiceBtn.setAttribute('title', 'Click to speak (Voice input)');
                    }
                    if (this.mediaStream) {
                        this.mediaStream.getTracks().forEach(track => track.stop());
                        this.mediaStream = null;
                    }

                    const recordedMime = this.mediaRecorder.mimeType || 'audio/webm';
                    const audioBlob = new Blob(this.audioChunks, { type: recordedMime });
                    this.sendVoiceMessage(audioBlob);
                };

                this.mediaRecorder.start(200);
            } catch (err) {
                console.error('[AgentChat] Microphone permission denied or error:', err);
                this.showToast('Microphone access was denied or unavailable.');
                this.isRecording = false;
                if (this.elements.voiceBtn) {
                    this.elements.voiceBtn.classList.remove('is-recording');
                }
            }
        }

        stopRecording() {
            if (this.mediaRecorder && this.isRecording) {
                try {
                    this.mediaRecorder.stop();
                } catch (e) {
                    console.warn('[AgentChat] Error stopping MediaRecorder:', e);
                }
            }
        }

        async sendVoiceMessage(audioBlob) {
            if (!audioBlob || audioBlob.size < 1200) {
                this.showToast('No speech detected. Please speak clearly into your mic.');
                return;
            }

            this.isProcessingVoice = true;
            if (this.elements.voiceBtn) {
                this.elements.voiceBtn.classList.add('is-processing');
                this.elements.voiceBtn.setAttribute('title', 'Processing your voice message...');
            }

            // Hide welcome suggestions if first message
            if (this.elements.welcomeContainer) {
                this.elements.welcomeContainer.style.display = 'none';
            }

            const typingIndicator = this.showTypingIndicator();
            this.showToast('Processing voice with Faster-Whisper...');

            try {
                // Read audioBlob as Base64 Data URL
                const reader = new FileReader();
                const base64Promise = new Promise((resolve, reject) => {
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(audioBlob);
                });

                const base64Audio = await base64Promise;

                const payload = {
                    audio_base64: base64Audio,
                    session_id: this.sessionId
                };

                const voiceUrl = `${this.config.apiProxyUrl}?action=voice`;
                const res = await fetch(voiceUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                typingIndicator.remove();

                if (res.ok && data && data.data) {
                    const transcript = data.data.user_transcript || '🎤 [Voice question]';
                    const responseText = data.data.Response || '';
                    const audioUri = data.data.audio_base64 || null;

                    // 1. Render user speech transcript bubble
                    this.appendUserMessage(transcript);

                    // 2. Render AI assistant response with voice metadata
                    const assistantRow = this.appendAssistantMessage(responseText, {
                        isVoice: true,
                        audioDataUri: audioUri
                    });

                    // 3. Update active session id
                    if (data.data.session_id) {
                        this.sessionId = data.data.session_id;
                    }

                    // 4. Auto-play human-like speech response
                    if (audioUri) {
                        this.playAudioResponse(audioUri, assistantRow);
                    }
                } else {
                    const fallback = (data && data.data && data.data.Response) ||
                        "I had trouble understanding your voice message. Please try speaking again or type your question.";
                    this.appendAssistantMessage(fallback);
                }
            } catch (err) {
                console.error('[AgentChat] Voice request error:', err);
                typingIndicator.remove();
                this.appendAssistantMessage(
                    "I'm having trouble connecting to the voice assistant. Please check your internet connection or type below."
                );
            } finally {
                this.isProcessingVoice = false;
                if (this.elements.voiceBtn) {
                    this.elements.voiceBtn.classList.remove('is-processing');
                    this.elements.voiceBtn.setAttribute('title', 'Click to speak (Voice input)');
                }
                this.scrollToBottom();
            }
        }

        showTypingIndicator() {
            const row = document.createElement('div');
            row.className = 'sophie-msg-row sophie-msg-assistant sophie-typing-row';

            const bubble = document.createElement('div');
            bubble.className = 'sophie-msg-bubble sophie-typing';
            bubble.innerHTML = `
                <div class="sophie-typing-dot"></div>
                <div class="sophie-typing-dot"></div>
                <div class="sophie-typing-dot"></div>
            `;

            row.appendChild(bubble);
            this.elements.messagesStream.appendChild(row);
            this.scrollToBottom();

            return row;
        }

        setSubmitting(isSubmitting) {
            this.isSubmitting = isSubmitting;
            if (this.elements.sendBtn) {
                this.elements.sendBtn.disabled = isSubmitting;
            }
            if (this.elements.input) {
                this.elements.input.disabled = isSubmitting;
                if (!isSubmitting) {
                    this.elements.input.focus();
                }
            }
        }

        scrollToBottom() {
            if (!this.config.autoScroll || !this.elements.body) return;
            requestAnimationFrame(() => {
                this.elements.body.scrollTop = this.elements.body.scrollHeight;
            });
        }

        showToast(msg) {
            if (!this.elements.toast) return;
            this.elements.toast.textContent = msg;
            this.elements.toast.classList.add('is-active');
            clearTimeout(this._toastTimer);
            this._toastTimer = setTimeout(() => {
                this.elements.toast.classList.remove('is-active');
            }, 2600);
        }

        getCurrentTimeString() {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const mins = String(now.getMinutes()).padStart(2, '0');
            return `${hours}:${mins}`;
        }

        formatMarkdown(text) {
            if (!text) return '';

            // Escape basic HTML to prevent XSS
            let safe = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // Headers (### Header)
            safe = safe.replace(/^### (.*$)/gim, '<h4 style="font-size:14px; font-weight:700; margin:8px 0 4px;">$1</h4>');
            safe = safe.replace(/^## (.*$)/gim, '<h3 style="font-size:15px; font-weight:700; margin:10px 0 4px;">$1</h3>');

            // Bold **text**
            safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

            // Italic *text*
            safe = safe.replace(/\*(.*?)\*/g, '<em>$1</em>');

            // Markdown Links [title](url)
            safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

            // Bullet lists (* item or - item)
            safe = safe.replace(/^\s*[\-\*]\s+(.*$)/gim, '<li>$1</li>');
            safe = safe.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');

            // Line breaks
            safe = safe.replace(/\n\n+/g, '</p><p>');
            safe = safe.replace(/\n/g, '<br>');

            return `<p>${safe}</p>`;
        }

        getOrCreateSessionId() {
            const key = this.config.storagePrefix + 'session_id';
            let id = null;
            try {
                id = localStorage.getItem(key);
            } catch (e) {}

            if (!id || !/^[0-9a-fA-F-]{8,40}$/.test(id)) {
                id = this.generateUuid();
                try {
                    localStorage.setItem(key, id);
                } catch (e) {}
            }
            return id;
        }

        generateUuid() {
            if (typeof crypto !== 'undefined' && crypto.randomUUID) {
                return crypto.randomUUID();
            }
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        window.SophieChat = new SophieAgentChatbot();
    });

})();
