<?php
/**
 * Surfaces Tiles UK - AI Agent Chatbot Test & Integration Harness
 * 
 * Demonstrates the modern Agent chatbot component placed in the website footer
 * and as a floating widget, matching the reference design without affecting site styles.
 */

// Allow toggling test mode via ?mode=card or ?mode=floating
$testMode = isset($_GET['mode']) && $_GET['mode'] === 'card' ? 'card' : 'floating';
$chatbot_mode = $testMode;
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Surfaces Tiles UK - AI Agent Chatbot UI</title>
    
    <!-- Test Page Styling (Simulates modern website environment) -->
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #F8FAFC;
            color: #0F172A;
            line-height: 1.6;
        }

        /* Developer Test Toolbar */
        .dev-toolbar {
            background: #0F172A;
            color: #F8FAFC;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            font-size: 13px;
        }
        .dev-toolbar a {
            color: #A78BFA;
            text-decoration: none;
            font-weight: 600;
        }
        .dev-mode-selector {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .dev-btn {
            background: #1E293B;
            color: #E2E8F0;
            padding: 6px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 12px;
            font-weight: 500;
            border: 1px solid #334155;
            transition: all 0.2s;
        }
        .dev-btn.active {
            background: #7C3AED;
            color: #FFFFFF;
            border-color: #7C3AED;
            font-weight: 700;
        }

        /* Simulated Existing Site Layout */
        .site-header {
            background: #FFFFFF;
            border-bottom: 1px solid #E2E8F0;
            padding: 18px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .site-logo {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #0F172A;
            text-decoration: none;
        }
        .site-nav {
            display: flex;
            gap: 24px;
            list-style: none;
        }
        .site-nav a {
            color: #475569;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
        }
        .site-nav a:hover {
            color: #0F172A;
        }

        .site-main {
            max-width: 1140px;
            margin: 40px auto;
            padding: 0 24px;
        }
        .site-hero {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 20px;
            padding: 40px 36px;
            margin-bottom: 32px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.03);
        }
        .site-hero h1 {
            font-size: 30px;
            font-weight: 800;
            margin-bottom: 12px;
            color: #0F172A;
            letter-spacing: -0.02em;
        }
        .site-hero p {
            color: #64748B;
            font-size: 15px;
            max-width: 720px;
        }

        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 36px;
        }
        .feature-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            padding: 24px;
        }
        .feature-icon {
            font-size: 24px;
            margin-bottom: 10px;
        }
        .feature-title {
            font-size: 16px;
            font-weight: 700;
            color: #0F172A;
            margin-bottom: 6px;
        }
        .feature-desc {
            font-size: 13.5px;
            color: #64748B;
            line-height: 1.5;
        }

        .integration-guide {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 20px;
            padding: 32px;
            margin-bottom: 40px;
        }
        .integration-guide h2 {
            font-size: 19px;
            font-weight: 700;
            margin-bottom: 12px;
        }
        .code-box {
            background: #0F172A;
            color: #A78BFA;
            padding: 14px 18px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
            overflow-x: auto;
            margin: 12px 0 16px 0;
        }

        /* Simulated Existing Site Footer Area */
        .site-footer {
            background: #0B1329;
            color: #CBD5E1;
            padding: 56px 32px 36px 32px;
            margin-top: 60px;
        }
        .footer-inner {
            max-width: 1140px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 40px;
            padding-bottom: 40px;
            border-bottom: 1px solid #1E293B;
        }
        .footer-col h3 {
            color: #FFFFFF;
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 16px;
        }
        .footer-col ul {
            list-style: none;
        }
        .footer-col li {
            margin-bottom: 10px;
            font-size: 14px;
        }
        .footer-col a {
            color: #94A3B8;
            text-decoration: none;
        }
        .footer-col a:hover {
            color: #FFFFFF;
        }

        /* Chatbot test embed container in footer area */
        .footer-chatbot-test-container {
            max-width: 1140px;
            margin: 36px auto 0 auto;
            background: #111C3A;
            border: 1px dashed #334155;
            border-radius: 24px;
            padding: 32px;
            text-align: center;
        }
        .footer-chatbot-badge {
            display: inline-block;
            background: #1E293B;
            color: #A78BFA;
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 24px;
        }
    </style>
</head>
<body>

    <!-- Test Mode Switcher Toolbar -->
    <div class="dev-toolbar">
        <div>
            <strong>Surfaces Tiles UK</strong> &mdash; Modern AI Agent Chatbot UI
        </div>
        <div class="dev-mode-selector">
            <span>Display Mode:</span>
            <a href="?mode=widget" class="dev-btn <?php echo $testMode === 'floating' ? 'active' : ''; ?>">Floating Widget Mode</a>
            <a href="?mode=card" class="dev-btn <?php echo $testMode === 'card' ? 'active' : ''; ?>">Embedded Card Mode</a>
        </div>
    </div>

    <!-- Simulated Existing Website Header -->
    <header class="site-header">
        <a href="#" class="site-logo">SURFACES TILES</a>
        <nav>
            <ul class="site-nav">
                <li><a href="#">Floor Tiles</a></li>
                <li><a href="#">Wall Tiles</a></li>
                <li><a href="#">Outdoor &amp; Patio</a></li>
                <li><a href="#">Kitchen &amp; Bathroom</a></li>
                <li><a href="#">Showroom</a></li>
            </ul>
        </nav>
    </header>

    <!-- Simulated Website Content -->
    <main class="site-main">
        <div class="site-hero">
            <h1>Luxury Porcelain &amp; Natural Stone Collections</h1>
            <p>Experience the new AI Agent shopping assistant designed with structured information cards, interactive row navigation, speech synthesis, and real-time voice input.</p>
        </div>

        <!-- UI Capabilities Grid -->
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">💳</div>
                <div class="feature-title">Structured Data Cards</div>
                <div class="feature-desc">Interactive rows with dedicated action chevrons for rapid account, invoice, or tile inquiry.</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🎙️</div>
                <div class="feature-title">Gradient Ring Voice Input</div>
                <div class="feature-desc">Hands-free speech-to-text dictation with live listening animation and text auto-fill.</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔊</div>
                <div class="feature-title">Audio &amp; Quick Actions</div>
                <div class="feature-desc">Text-to-speech speaker button, 1-click clipboard copy, and stacked quick action capsules.</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">Skills &amp; Agent Switcher</div>
                <div class="feature-desc">Switch specialized assistant modes and access domain skills with one click.</div>
            </div>
        </div>

        <div class="integration-guide">
            <h2>Quick 1-Line Integration</h2>
            <p>Include the self-contained component in any PHP template or footer:</p>
            <div class="code-box">&lt;?php include __DIR__ . '/frontend/chatbot.php'; ?&gt;</div>
            <p style="color: #64748B; font-size: 13.5px;">CSS and JavaScript are strictly isolated to avoid conflicting with existing site frameworks.</p>
        </div>
    </main>

    <!-- Simulated Website Footer Area -->
    <footer class="site-footer">
        <div class="footer-inner">
            <div class="footer-col">
                <h3>Surfaces Tiles UK</h3>
                <p style="font-size: 14px; line-height: 1.6; color: #94A3B8;">
                    London's trusted destination for high-performance porcelain, marble-effect slabs, and outdoor patio paving.
                </p>
            </div>
            <div class="footer-col">
                <h3>Customer Care</h3>
                <ul>
                    <li><a href="#">Order Tile Samples</a></li>
                    <li><a href="#">Delivery &amp; Collection</a></li>
                    <li><a href="#">Returns &amp; Refunds</a></li>
                    <li><a href="#">VAT Invoices &amp; Billing</a></li>
                </ul>
            </div>
            <div class="footer-col">
                <h3>Contact &amp; Showroom</h3>
                <ul>
                    <li>Showroom: Edgware Road, London NW2</li>
                    <li>Phone: 020 8452 4688</li>
                    <li>Email: sales@surfacestiles.co.uk</li>
                    <li>Mon - Sat: 8:00am - 5:30pm</li>
                </ul>
            </div>
        </div>

        <!-- Chatbot Component Tested in Footer -->
        <?php if ($testMode === 'card'): ?>
        <div class="footer-chatbot-test-container">
            <div class="footer-chatbot-badge">Embedded Card Preview Mode</div>
            <?php include __DIR__ . '/chatbot.php'; ?>
        </div>
        <?php else: ?>
        <!-- Floating Chatbot Component -->
        <?php include __DIR__ . '/chatbot.php'; ?>
        <?php endif; ?>

        <div style="text-align: center; font-size: 12px; color: #64748B; margin-top: 36px;">
            &copy; <?php echo date('Y'); ?> Surfaces Tiles UK. All rights reserved.
        </div>
    </footer>

</body>
</html>
