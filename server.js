import axios from 'axios';
import express from 'express';
import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import fs from 'fs';

const { Client, LocalAuth, MessageMedia } = pkg;

const app = express();

app.use(express.json());

const USERS_PATH = '/config/users.json';

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

client.on('loading_screen', (percent, message) => {
    if (isReady) return;

    const totalBars = 20;
    const completed = Math.round((percent / 100) * totalBars);
    const remaining = totalBars - completed;
    
    const progressBar = '█'.repeat(completed) + '░'.repeat(remaining);
    
    console.log(`⏳ [PROGRESS] WhatsApp Loading: [${progressBar}] ${percent}% | ${message}`);
});

client.on('ready', () => {
    isReady = true;
    console.log('✅ [READY] Raspiflix WhatsApp Gateway ONLINE and ready to send alerts!');
});

client.on('authenticated', () => {
    console.log('🔐 [AUTH] Existing WhatsApp session detected and successfully authenticated!');
});

client.on('auth_failure', msg => {
    console.error('❌ [ERROR] Authentication failure:', msg);
});

client.on('disconnected', reason => {
    console.error('⚠️ [WARN] WhatsApp disconnected:', reason);
});

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

client.initialize();

app.post('/send-media', async (request, response) => {
    try {
        const {
            to,
            caption,
            image_url
        } = request.body;

        if (!to) {
            return response.status(400).json({
                error: 'Missing "to" field'
            });
        }

        if (!isReady) {
            return response.status(503).json({
                error: 'WhatsApp Client is not ready yet'
            });
        }

        const normalizedTo = to.replace(/\D/g, '');
        const chatId = `${normalizedTo}@c.us`;

        const media = await getMediaFromUrl(image_url);

        return response.status(503).json({
            error: 'WhatsApp Client is not ready yet'
        });

        await client.sendMessage(
            chatId,
            media,
            { caption: caption }
        );

        response.json({
            success: true
        });
    } catch (err) {
        console.error(err);

        response.status(500).json({
            error: err.message
        });
    }
});

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

app.listen(3000, () => {
    console.log('📡 WhatsApp listening on port 3000...');
});
