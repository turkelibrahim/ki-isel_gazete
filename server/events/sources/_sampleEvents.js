function daysFromNow(days, hour = 20, minute = 0) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

function sampleEventsForSource(sourceName) {
  const base = [
    {
      sourceEventId: "yalin-parca-pincik-akustik",
      title: "Yalın - Parça Pinçik Akustik",
      description: "Sevilen sanatçıdan akustik sahne performansı ve özel repertuvar.",
      category: "Konser",
      startDate: daysFromNow(4, 21, 0),
      city: "İstanbul",
      district: "Beşiktaş",
      venueName: "Zorlu PSM Turkcell Sahnesi",
      venueAddress: "Zorlu Center, Beşiktaş",
      priceMin: 650,
      priceMax: 1450,
      ticketUrl: "https://www.biletix.com/",
      imageUrl: "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=1100&q=80",
      tags: ["konser", "akustik", "müzik"],
      popularityScore: 92
    },
    {
      sourceEventId: "bir-delinin-hatira-defteri",
      title: "Bir Delinin Hatıra Defteri",
      description: "Klasikleşmiş tiyatro oyunu, güçlü oyunculuk ve sade sahne tasarımıyla izleyiciyle buluşuyor.",
      category: "Tiyatro",
      startDate: daysFromNow(5, 20, 30),
      city: "İstanbul",
      district: "Şişli",
      venueName: "DasDas",
      priceMin: 350,
      priceMax: 750,
      ticketUrl: "https://bubilet.com.tr/",
      imageUrl: "https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&fit=crop&w=1100&q=80",
      tags: ["tiyatro", "sahne"],
      popularityScore: 84
    },
    {
      sourceEventId: "hayal-fest-2024",
      title: "Hayal Fest 2024",
      description: "Müzik, sahne ve açık hava deneyimini bir araya getiren şehir festivali.",
      category: "Festival",
      startDate: daysFromNow(6, 16, 0),
      city: "Sarıyer",
      district: "Sarıyer",
      venueName: "Bonus Parkorman",
      priceMin: 550,
      priceMax: 1200,
      ticketUrl: "https://www.passo.com.tr/",
      imageUrl: "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=1100&q=80",
      tags: ["festival", "konser"],
      popularityScore: 90
    },
    {
      sourceEventId: "tolga-cevik-stand-up",
      title: "Tolga Çevik - Stand-up Gösterisi",
      description: "Komedi sahnesinden yüksek tempolu ve interaktif bir gösteri.",
      category: "Stand-up",
      startDate: daysFromNow(8, 21, 0),
      city: "İstanbul",
      district: "Maslak",
      venueName: "Maximum Uniq Hall",
      priceMin: 400,
      priceMax: 950,
      ticketUrl: "https://www.biletinial.com/",
      imageUrl: "https://images.unsplash.com/photo-1527224857830-43a7acc85260?auto=format&fit=crop&w=1100&q=80",
      tags: ["stand-up", "komedi"],
      popularityScore: 82
    },
    {
      sourceEventId: "fenerbahce-galatasaray",
      title: "Fenerbahçe - Galatasaray",
      description: "Sezonun en çok beklenen futbol karşılaşması için biletler satışta.",
      category: "Spor",
      startDate: daysFromNow(9, 20, 0),
      city: "İstanbul",
      district: "Kadıköy",
      venueName: "Ülker Stadyumu",
      priceMin: 750,
      priceMax: 2500,
      ticketUrl: "https://www.passo.com.tr/",
      imageUrl: "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=1100&q=80",
      tags: ["spor", "futbol"],
      popularityScore: 95
    },
    {
      sourceEventId: "istanbul-resim-heykel-muzesi",
      title: "İstanbul Resim ve Heykel Müzesi",
      description: "Daimi koleksiyon ve seçili sergi programı sanatseverlerle buluşuyor.",
      category: "Sergi",
      startDate: daysFromNow(10, 11, 0),
      city: "İstanbul",
      district: "Beyoğlu",
      venueName: "İstanbul Resim ve Heykel Müzesi",
      priceMin: 0,
      priceMax: 0,
      ticketUrl: "https://kultur.istanbul/",
      imageUrl: "https://images.unsplash.com/photo-1518998053901-5348d3961a04?auto=format&fit=crop&w=1100&q=80",
      tags: ["sergi", "müze"],
      popularityScore: 70
    }
  ];

  return base.map((event, index) => ({
    ...event,
    sourceName,
    sourceEventId: `${event.sourceEventId}-${sourceName.toLocaleLowerCase("tr-TR").replace(/\s+/g, "-")}`,
    ticketUrl: sourceTicketUrl(sourceName, event.ticketUrl),
    priceMin: event.priceMin === null ? null : Math.max(0, Math.round((event.priceMin || 0) * (1 + index * 0.01))),
    popularityScore: event.popularityScore - index
  }));
}

function sourceTicketUrl(sourceName, fallback) {
  const map = {
    "Biletix": "https://www.biletix.com/",
    "Bubilet": "https://www.bubilet.com.tr/",
    "Passo": "https://www.passo.com.tr/",
    "Mobilet": "https://mobilet.com/",
    "Biletinial": "https://biletinial.com/tr-tr",
    "Ticketmaster": "https://www.ticketmaster.com/",
    "Eventbrite": "https://www.eventbrite.com/",
    "Meetup": "https://www.meetup.com/",
    "Kültür İstanbul": "https://kultur.istanbul/",
    "İBB Kültür Sanat": "https://kultursanat.istanbul/etkinliklerimiz",
    "Zorlu PSM": "https://www.zorlupsm.com/etkinlikler",
    "AKM İstanbul": "https://akmistanbul.gov.tr/tr/etkinlikler",
    "Etkinlik.io": "https://etkinlik.io/",
    "Festivall": "https://festivall.com.tr/"
  };
  return map[sourceName] || fallback || "";
}

module.exports = { sampleEventsForSource };
