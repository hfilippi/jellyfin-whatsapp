import axios from 'axios';
import express from 'express';
import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import fs from 'fs';

const { Client, LocalAuth, MessageMedia } = pkg;

const app = express();
app.use(express.json());

const USERS_PATH = '/config/users.json';
const CONFIG_PATH = '/config/config.json';
const TEMPLATES_PATH = '/config/templates.json';

let finalStructureTemplate = "{{caption}}{{trailer}}{{unsubscribe}}";
let tmdbConfig = {};

// Load templates and TMDB config on startup, with error handling and fallbacks
function loadConfigsOnStartup() {
    // Load templates with fallback to default structure
    if (fs.existsSync(TEMPLATES_PATH)) {
        try {
            const templates = JSON.parse(fs.readFileSync(TEMPLATES_PATH, 'utf8'));
            finalStructureTemplate = templates.final_structure || finalStructureTemplate;
        } catch (error) {
            console.error('⚠️ [WARN] Failed to parse templates.json, using default structure:', error);
        }
    }

    // Load TMDB config with error handling and default values
    if (fs.existsSync(CONFIG_PATH)) {
        try {
            const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
            tmdbConfig = config.tmdb || {};
        } catch (error) {
            console.error('⚠️ [WARN] Failed to parse config.json:', error);
        }
    }
}

// Call the function to load configs on startup
loadConfigsOnStartup();

// Initialize WhatsApp client with local authentication and optimized Puppeteer settings for headless environments
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: '/data/session'
    }),
    puppeteer: {
        headless: true,
        executablePath: process.env.CHROME_BIN || '/usr/bin/chromium-shell',
        timeout: 180000,
        protocolTimeout: 180000,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-extensions',
            '--ignore-certificate-errors',
            '--no-default-browser-check'
        ]
    }
});

// Event listeners for WhatsApp client lifecycle and message handling
client.on('qr', (qr) => {
    console.log('\n📲 [AUTH_NEEDED] Session not found! Generating QR code to scan...\n');

    console.log('\n==============================');
    console.log('\n========== SCAN  QR ==========\n');
    console.log('==============================\n');

    qrcode.generate(qr, {
        small: true
    });
});

let isReady = false;

console.log('🚀 [INIT] Launching Chromium and connecting to browser...');

// Show loading progress with a dynamic progress bar in the console, only if the client is not ready yet
client.on('loading_screen', (percent, message) => {
    if (isReady) return;

    const totalBars = 20;
    const completed = Math.round((percent / 100) * totalBars);
    const remaining = totalBars - completed;
    
    const progressBar = '█'.repeat(completed) + '░'.repeat(remaining);
    
    console.log(`⏳ [PROGRESS] WhatsApp Loading: [${progressBar}] ${percent}% | ${message}`);
});

// Handle client ready event with a flag to prevent multiple logs and ensure the client is fully ready before accepting requests
client.on('ready', () => {
    isReady = true;
    console.log('✅ [READY] Raspiflix WhatsApp Gateway ONLINE and ready to send alerts!');
});

// Handle existing authenticated sessions without requiring QR code scanning, with informative logging
client.on('authenticated', () => {
    console.log('🔐 [AUTH] Existing WhatsApp session detected and successfully authenticated!');
});

// Handle authentication failures with detailed error logging for easier troubleshooting
client.on('auth_failure', msg => {
    console.error('❌ [ERROR] Authentication failure:', msg);
});

// Handle client disconnection with error logging and potential auto-restart logic (if needed in the future)
client.on('disconnected', reason => {
    console.error('⚠️ [WARN] WhatsApp disconnected:', reason);
});

// Handle incoming messages for unsubscription requests, with robust phone number matching and error handling
client.on('message', async msg => {
    if (msg.body.toLowerCase().startsWith('unsubscribe')) {
        const senderPhone = msg.from.replace(/\D/g, '');

        if (senderPhone) {
            try {
                let users = JSON.parse(fs.readFileSync(USERS_PATH, 'utf8'));                
                let userUpdated = false;

                const updatedUsers = users.map(user => {
                    const cleanUserPhone = user.phone.slice(-10);
                    const cleanSenderPhone = senderPhone.slice(-10);

                    if (cleanUserPhone === cleanSenderPhone) {
                        if (user.enabled !== false) {
                            user.enabled = false;
                            userUpdated = true;
                        }
                    }
                    return user;
                });

                if (userUpdated) {
                    fs.writeFileSync(USERS_PATH, JSON.stringify(updatedUsers, null, 4));
                    await msg.reply('👋🏻 Fuiste dado de baja de las notificaciones.');
                    console.log(`🔕 User ${senderPhone} unsubscribed successfully`);
                } else {
                    console.log(`⚠️ The number ${senderPhone} sent "unsubscribe" but was not active or not found in users.json`);
                }
            } catch (error) {
                console.error('💥 Error processing the unsubscribe:', error);
            }
        }
    }
});

// Start the WhatsApp client
client.initialize();

// API endpoint to receive media sending requests from the Python app
app.post('/send-media', async (request, response) => {
    try {
        const {
            to,
            caption,
            image_url,
            tmdb_id,
            unsubscribe_link
        } = request.body;

        if (!to) {
            return response.status(400).json({ error: 'Missing "to" field' });
        }

        if (!isReady) {
            return response.status(503).json({ error: 'WhatsApp Client is not ready yet' });
        }

        const normalizedTo = to.replace(/\D/g, '');
        const chatId = `${normalizedTo}@c.us`;

        // Get media from URL and trailer URL (if tmdb_id is provided)
        const media = await getMediaFromUrl(image_url);
        const trailerUrl = await getTrailerUrl(tmdb_id);

        let fullCaption = finalStructureTemplate
            .replace("{{caption}}", caption)
            .replace("{{trailer}}", trailerUrl ? `\n\n🎬 Trailer: ${trailerUrl}` : '')
            .replace("{{unsubscribe}}", unsubscribe_link ? unsubscribe_link : '');

        await client.sendMessage(chatId, media, { caption: fullCaption });

        response.json({ success: true });
    } catch (err) {
        console.error(err);
        response.status(500).json({ error: err.message });
    }
});

// Helper function to download media from a URL and convert it to MessageMedia format
async function getMediaFromUrl(url) {
    try {
        const response = await axios.get(url, {
            responseType: 'arraybuffer',
            timeout: 15000
        });

        const mimeType = response.headers['content-type'];

        return new MessageMedia(mimeType, Buffer.from(response.data).toString('base64'), "media.jpg");
    } catch (err) {
        console.error('❌ Failed to download media from URL:', url);
        throw err;
    }
}

// Helper function to fetch trailer URL from TMDB API based on tmdbId, with support for language fallback and error handling
async function getTrailerUrl(tmdbId) {
    if (!tmdbId) return null;

    try {
        if (tmdbConfig.send_trailers === false) {
            return null;
        }

        const tmdbApiKey = tmdbConfig.api_key;
        const lang = tmdbConfig.language || 'en';

        if (!tmdbApiKey) {
            console.error('⚠️ [WARN] TMDB API Key is missing in config.json');
            return null;
        }

        // First try to get trailer in specified language
        let tmdbResponse = await axios.get(`https://api.themoviedb.org/3/movie/${tmdbId}/videos`, {
            params: { api_key: tmdbApiKey, language: lang }
        });

        // Look for a YouTube trailer
        let video = tmdbResponse.data.results.find(v => v.type === 'Trailer' && v.site === 'YouTube');

        // If no trailer found in specified language, try fallback to English
        if (!video && lang !== 'en') {
            console.log(`ℹ️ [TMDB] No trailer found in '${lang}'. Trying fallback to 'en'...`);
            tmdbResponse = await axios.get(`https://api.themoviedb.org/3/movie/${tmdbId}/videos`, {
                params: { api_key: tmdbApiKey, language: 'en' }
            });
            video = tmdbResponse.data.results.find(v => v.type === 'Trailer' && v.site === 'YouTube');
        }

        console.log(`🎬 [TMDB] Trailer fetch for TMDB ID ${tmdbId}: ${video ? 'Found' : 'Not Found'}`);

        return video ? `https://youtu.be/${video.key}` : null;
    } catch (err) {
        console.error('⚠️ [WARN] Failed to fetch trailer from TMDB:', err.message);
        return null;
    }
}

// Start the Express server to listen for incoming requests from the Python app
app.listen(3000, () => {
    console.log('📡 WhatsApp listening on port 3000...');
});
