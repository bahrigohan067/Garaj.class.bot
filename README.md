# GararjClass Bot

## Kurulum ve Çalıştırma

1. Python 3.8 veya daha üstü bir sürümün yüklü olduğundan emin olun.
2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
3. `TOKEN` ortam değişkenini (environment variable) ayarlayın veya `config.py` içinde direkt olarak belirtebilirsiniz. GitHub'a yüklerken token'ın `config.py` içinde yazmamasına, ortam değişkenlerinde tutulmasına özen gösterin (örn: `.env` dosyası kullanarak).

### Komutlar ve Kullanımı:
- Botu çalıştırdıktan sonra, kayıt kanalına (`Kayıt Ol`) butonu göndermek için herhangi bir kanala `!kayitmesaji` yazabilirsiniz.
- Ticket kanalına butonu göndermek için `!ticketmesaji` yazabilirsiniz.
- Tabloyu test etmek isterseniz (gece 00:00'ı beklemeden), `!zorlaleaderboard` yazabilirsiniz.
- Ticket içinde başka birini bilet kanalına eklemek için `/ekle @kullanici` slash komutunu kullanabilirsiniz.

## Özellikler
- **Otomatik Rol & Karşılama:** Sunucuya giren kişilere "Unverified" rolü verilir ve hoşgeldin mesajı atılır.
- **Kayıt Sistemi:** Kayıt ol butonuna basan üyelerden Takma Ad ve Roblox profil linki istenir. Yetkililer Onay-Red kanalında değerlendirir, onaylanınca kullanıcının adı değişir ve yetkiler ayarlanır.
- **Ticket Sistemi:** Butonla destek bileti açılır.
- **Sesli Destek Bekleme Sistemi:** Bekleme odasına giren kullanıcılar susturulur ve yetkililere bildirim atılır. Yetkili onaylayınca destek odasına çekilirler.
- **Yetkili Aktivite Takibi:** Yetkililerin discordda aktif oldukları, ses kanalında durdukları, kapattıkları ticketlar ve bitirdikleri desteklerin kaydı tutulur ve her gece saat 00:00'da leaderboard paylaşılır.
