const fs = require('fs');
const https = require('https');
const http = require('http');

const demoPath = './db/demo-regional-pandemic.json';
let demoData = JSON.parse(fs.readFileSync(demoPath, 'utf8'));

// Mappings of sourceName to RSS URL
const rssUrls = {
  "NHK World": "https://www3.nhk.or.jp/rss/news/cat0.xml",
  "South China Morning Post": "https://www.scmp.com/rss/91/feed",
  "The Japan Times": "https://www.japantimes.co.jp/feed/",
  "BBC Europe": "http://feeds.bbci.co.uk/news/world/europe/rss.xml",
  "Deutsche Welle Europe": "https://rss.dw.com/rdf/rss-en-eu",
  "France 24 Europe": "https://www.france24.com/en/europe/rss",
  "CNN": "http://rss.cnn.com/rss/cnn_world.rss",
  "Associated Press": "https://feeds.apnews.com/rss/apf-topnews",
  "NPR": "https://feeds.npr.org/1004/rss.xml"
};

function fetchRssImage(url) {
    return new Promise((resolve) => {
        const client = url.startsWith('https') ? https : http;
        client.get(url, (res) => {
            let data = '';
            res.on('data', d => data += d);
            res.on('end', () => {
                // Extract media:content url, media:thumbnail url, enclosure url, or img src
                const match = data.match(/media:(content|thumbnail)[^>]*url=["']([^"']+)["']/i) ||
                              data.match(/enclosure[^>]*url=["']([^"']+)["']/i) ||
                              data.match(/<img[^>]+src=["'](https?:\/\/[^"']+)["']/i) ||
                              data.match(/<image>[\s\S]*?<url>(.*?)<\/url>[\s\S]*?<\/image>/i);
                if (match && match[2]) {
                    resolve(match[2]);
                } else if (match && match[1]) {
                    resolve(match[1]);
                } else {
                    resolve("");
                }
            });
        }).on('error', () => resolve(""));
    });
}

async function updateImages() {
    for (let article of demoData) {
        if (!article.imageUrl && rssUrls[article.sourceName]) {
            console.log(`Fetching image for ${article.sourceName}...`);
            const url = await fetchRssImage(rssUrls[article.sourceName]);
            if (url) {
                article.imageUrl = url;
                console.log(`Found: ${url}`);
            } else {
                console.log(`No image found.`);
                // Fallback image based on source
                if (article.sourceName.includes("BBC")) article.imageUrl = "https://m.files.bbci.co.uk/modules/bbc-morph-news-waf-page-meta/5.3.0/bbc_news_logo.png";
                else if (article.sourceName.includes("CNN")) article.imageUrl = "https://cdn.cnn.com/cnn/.e/img/3.0/global/misc/cnn-logo.png";
                else article.imageUrl = "https://images.unsplash.com/photo-1584483766114-2cea6facdf57?auto=format&fit=crop&w=800&q=80";
            }
        }
    }
    fs.writeFileSync(demoPath, JSON.stringify(demoData, null, 2));
    console.log("Updated demo data.");
}

updateImages();
