const fs = require('fs');

function decodeHtml(html) {
    if (!html) return "";
    return html.replace(/&amp;/g, "&")
               .replace(/&lt;/g, "<")
               .replace(/&gt;/g, ">")
               .replace(/&quot;/g, "\"")
               .replace(/&#039;/g, "'");
}

function stripHtml(html) {
    if (!html) return "";
    return html.replace(/<[^>]*>?/gm, '').trim();
}

function extractXmlTag(block, tagName) {
  const escaped = tagName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = block.match(new RegExp(`<${escaped}[^>]*>([\\s\\S]*?)<\\/${escaped}>`, "i"));
  if (!match) return "";
  // Strip CDATA wrappers used by CNN Turk, Sozcu etc: <![CDATA[...]]>
  const raw = match[1];
  const cdataMatch = raw.match(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/);
  const val = cdataMatch ? cdataMatch[1].trim() : raw.trim();
  return decodeHtml(val);
}

function extractXmlAttr(block, tagName, attrName) {
  const escapedTag = tagName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const escapedAttr = attrName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = block.match(new RegExp(`<${escapedTag}[^>]*\\s${escapedAttr}=["']([^"']+)["'][^>]*>`, "i"));
  return match ? decodeHtml(match[1]) : "";
}

function getArticleImageFromRssItem(block) {
  return extractXmlAttr(block, "media:content", "url")
    || extractXmlAttr(block, "media:thumbnail", "url")
    || extractXmlAttr(block, "enclosure", "url")
    || stripHtml(extractXmlTag(block, "image"))
    || "";
}

const https = require('https');
https.get('https://www.france24.com/en/europe/rss', (res) => {
    let data = '';
    res.on('data', d => data += d);
    res.on('end', () => {
        const itemBlocks = [...data.matchAll(/<item[\s\S]*?<\/item>/gi)].map((match) => match[0]);
        console.log("Total items:", itemBlocks.length);
        if (itemBlocks.length > 0) {
            console.log("First item image:", getArticleImageFromRssItem(itemBlocks[0]));
        }
    });
});
