# Meme Paper Trader — GitHub Pages + Actions

Монгол хэл дээрх, зөвхөн **paper-trading** зориулалттай эхний хувилбар. Утасны браузераар dashboard нээгдэнэ. Энэ нь бодит мөнгөөр арилжаа хийхгүй, wallet/private key шаардахгүй.

## Юу хийдэг вэ?
- DexScreener-ийн public token profile болон pair API-аас candidate хайна.
- Тохируулсан EVM chain дээрх хамгийн өндөр liquidity-тэй pair-ийг авч шалгана.
- Liquidity, 1h transaction count, 24h volume дээр суурилсан энгийн heuristic confidence/risk гаргана.
- Бүх шийдвэрийг `data/decisions.jsonl` файлд append хийж, dashboard-ийн `data/state.json`-ийг шинэчилнэ.
- GitHub Actions ойролцоогоор 30 минут тутамд ажиллахаар тохируулсан; Actions tab-аас гараар ажиллуулж болно.

## Чухал хязгаарлалт
- Энэ нь **AI model биш**; confidence нь энгийн heuristic тооцоо.
- Энэ хувилбарын `owner_renounced` болон `contract_has_code` утгууд баталгаажаагүй (`null`). Тиймээс хоёр hard gate нь санаатайгаар FAIL болж, bot BUY хийхгүй. Энэ нь эрсдэлтэй худалдан авалтыг дуурайж хийхээс хамгаалсан fail-closed тохиргоо.
- Owner renounced гэдгийг зөвхөн pair API-аас батлах боломжгүй. Production-д chain RPC, explorer/API, contract-specific checks болон honeypot/tax/sell simulation хэрэгтэй.
- Анхдагч chain `base`. Энэ нь Robinhood Chain тусгай интеграц биш. Бусад chain-ийн ID-г сонгохын өмнө DexScreener API тухайн chain-ийг дэмждэг эсэхийг шалга.
- GitHub Actions scheduled runs саатаж болно, 24/7 realtime service биш. Public API rate limit болон GitHub quota үйлчилнэ.
- Ашиг олох баталгаа байхгүй.

## Утаснаас тохируулах
1. GitHub-д нэвтэрч шинэ repository үүсгэ: `meme-paper-trader`. `README`, `.gitignore`, license автоматаар үүсгэхгүйгээр хоосон repo үүсгэхэд хамгийн амар.
2. ZIP-ийг задлаад бүх файлыг repo-ийн root руу upload хий. `.github/workflows/paper-bot.yml` файлын зам яг хэвээр байх ёстой.
3. Repo → **Settings → Pages** → **Deploy from a branch** → `main` branch, `/(root)` → Save.
4. Repo → **Actions** tab → workflow enable хийх асуулт гарвал enable хий.
5. **Actions → Paper Trading Scanner → Run workflow** гэж дар.
6. Pages-ийн Settings хэсэгт гарч ирсэн URL-ийг нээ. Dashboard 60 секунд тутам data-г дахин уншина.

## Хэрэв workflow push хийхэд алдаа гарвал
Repo → Settings → Actions → General → Workflow permissions → **Read and write permissions** сонгоод Save. Дараа нь workflow-г дахин ажиллуул.

## Тохиргоо
Workflow дотор `CHAIN_ID`, `PAPER_START_BALANCE`, `PAPER_TRADE_SIZE`, `MIN_LIQUIDITY_USD`, `MIN_CONFIDENCE`, `MAX_RISK_SCORE`, `MAX_CANDIDATES` утгуудыг өөрчилж болно. Өөрчлөхийн өмнө paper mode хэвээр байгаа эсэхийг шалга.

## Файлууд
- `index.html`: mobile dashboard
- `bot.py`: public API scanner + JSONL audit log
- `.github/workflows/paper-bot.yml`: scheduled/manual scan workflow
- `data/state.json`: dashboard-ийн хамгийн сүүлийн state
- `data/decisions.jsonl`: шийдвэрийн append-only log
