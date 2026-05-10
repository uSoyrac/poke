# Champion Poker Training OS - Backup

**Yedekleme Tarihi:** 2026-05-10

## Bu Yedek Nedir?

Bu yedek, Champion Poker Training OS projesinin 2026-05-10 tarihindeki durumunu içerir. Claude Code ile yapılan geliştirmelerin yedeğidir.

## Son Yapılan Geliştirmeler

### 1. Drill Library / Training Packs Filtreleri
- **Elo filtresi eklendi:** Positive Elo, Negative Elo, High Impact (>50), Low Impact (<-50)
- **Hands filtresi eklendi:** 50+ hands, 100+ hands, 200+ hands
- **Type filtresi:** Tournaments 8-Max, Cash Games 8-Max, Tournaments ICM, Tournaments Explo, Cash Games Explo, Cash Games 6-Max
- **Street filtresi:** All, Preflop, Postflop

### 2. Range Viewer Action-Frequency Matrix
- **ActionFrequencyMatrix sınıfı eklendi:** Her hand için fold/check/call/bet/raise/jam frekanslarını gösteren matrix
- **Action renkleri:** Fold (Kırmızı), Check (Gri), Call (Mavi), Bet (Yeşil), Raise (Turuncu), Jam (Mor)
- **Hand strength hesaplama:** Basit hand strength algoritması ile action distribution hesaplama
- **Legend:** Action renklerinin açıklaması

### 3. Decision Reviews Entegrasyonu
- **Tournament Simulator:** Kararlar decision_reviews tablosuna kaydediliyor
- **Fast Play Simulator:** Kararlar decision_reviews tablosuna kaydediliyor
- **ICM Trainer:** Kararlar decision_reviews tablosuna kaydediliyor

## Proje Yapısı

```
champion_poker_training_os/
├── app/
│   ├── ui/screens/
│   │   ├── drill_builder.py          # Drill builder ve training pack library
│   │   ├── fast_play_simulator.py    # Fast-fold style rapid hand training
│   │   ├── tournament_simulator.py   # MTT tournament simulator
│   │   ├── icm_trainer.py            # ICM training
│   │   └── range_viewer.py           # Range viewer with action-frequency matrix
│   ├── training/
│   │   └── decision_review.py        # Decision review analysis
│   └── db/
│       └── repository.py             # Database operations
```

## Kullanım

```bash
# Proje dizinine git
cd "/Users/uygar/Documents/New project/poke"

# Yedeği geri yükle
git checkout claude/friendly-torvalds-0ecc83
```

## Notlar

- Bu yedek Claude Code ile otomatik olarak oluşturulmuştur
- Geliştirmeler devam etmektedir
- Yeni özellikler eklendikçe yedekler güncellenecektir
