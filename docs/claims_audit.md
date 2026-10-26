# Claims audit

Every number in the README, the result it comes from and the value recomputed from `docs/results.json` (written by `scripts/make_figures.py --refresh` from `data/public/`). `python scripts/audit_claims.py` regenerates this file and fails if a phrase is missing from the README or its numbers differ from the results.

101 claims checked, 101 verified.

| Section | README text | Source | Recomputed values | OK |
|:--|:--|:--|:--|:-:|
| Intro | followed **31,498** US Apple Watch listings | `overview.listings` | 31,498 | ✓ |
| Intro | It recorded **458,087** price snapshots and **3,843** listing outcomes, including **2,063 completed sales** | `overview.snapshots / outcomes / outcome_counts.sold` | 458,087, 3,843, 2,063 | ✓ |
| Intro | one week of data with 51 hours of collection gaps | `overview.gap_hours` | 51 | ✓ |
| Intro | the outdated Series 2 ($743), Series 4 ($676) and Series 3 ($664) averaged higher asking prices than the current Ultra 3 ($651) | `data/public/part1_model_prices.csv` | $743, $676, $664, $651 | ✓ |
| Intro | analyzed 2,328 web-scraped Apple Watch listings | `Part I README: 2,263 listings with a model (sum of part1_n) + 65 with none` | 2,328 | ✓ |
| Headline | \| **31,498** \| **458,087** \| **2,063** \| **724** \| **20,109** \| | `overview; auctions.n; sellers.n_sellers` | 31,498, 458,087, 2,063, 724, 20,109 | ✓ |
| Headline | A used Series 3 is listed at a median of $75 but sells for $35, **2.14×** its sale price (95% CI 1.88–2.34) | `ask_used[Series 3]` | $75, $35, 2.14, 1.88–2.34 | ✓ |
| Headline | For a used Ultra 3 the gap is only 1.07× (1.01–1.10) | `ask_used[Ultra 3]` | 1.07, 1.01–1.10 | ✓ |
| Headline | sell for a median of **$35–50** on eBay, against about $500 for the Ultra 3 | `bridge.part2_median_sold` | $35, 50, $500 | ✓ |
| Headline | were **41%** sold within 72 hours; those priced above 150% were **7%** sold (log-rank p = 8.7e-49) | `survival.table / logrank_p` | 41%, 7%, 8.7e-49 | ✓ |
| Headline | None of the **299** 24k gold listings ended or sold during the week. They ask a median of **$1,199**, **13.5×** what the same model sells for, and have been up for a median of **4.1 years**. Three sellers account for 95% of them. | `gold.n / ended / sold / median_ask / median_sold_ratio / median_age_years / top3_share` | 299, $1,199, 13.5, 4.1, 95% | ✓ |
| Headline | 51.5% of ended auctions sold. Series 9 and 10 auctions sold 63% of the time against 36% for the Series 3 (p = 0.0004). The median current bid 24–48 hours before the end is 76% of the final price. | `auctions.rate / new_vs_s3; trajectories.table` | 51.5%, 63%, 36%, 0.0004, 76% | ✓ |
| Headline | reaches R² = 0.90 (median error 14.7%) | `price_model.metrics` | 0.90, 14.7% | ✓ |
| Headline | Auctions sell for about $14 less | `price_model.format_shap[Auction]` | $14 | ✓ |
| Asking vs sold | Intervals are from 4,000 bootstrap resamples | `src/stats.py boot_ci n_boot` | 4,000 | ✓ |
| Asking vs sold | \| Series 3 \| $75 \| $35 \| 2.14 [1.88–2.34] \| 81 \| | `ask_used[Series 3]` | 2.14, 81 | ✓ |
| Asking vs sold | \| Series 4 \| $89 \| $45.25 \| 1.97 [1.70–2.25] \| 50 \| | `ask_used[Series 4]` | 1.97, 50 | ✓ |
| Asking vs sold | \| Series 6 \| $119.95 \| $65 \| 1.85 [1.70–1.92] \| 80 \| | `ask_used[Series 6]` | 1.85, 80 | ✓ |
| Asking vs sold | \| Series 9 \| $200 \| $130 \| 1.54 [1.44–1.59] \| 107 \| | `ask_used[Series 9]` | 1.54, 107 | ✓ |
| Asking vs sold | \| Series 10 \| $245 \| $180 \| 1.36 [1.23–1.41] \| 111 \| | `ask_used[Series 10]` | 1.36, 111 | ✓ |
| Asking vs sold | \| Series 11 \| $277 \| $230 \| 1.20 [1.13–1.23] \| 80 \| | `ask_used[Series 11]` | 1.20, 80 | ✓ |
| Asking vs sold | \| Ultra 1 \| $328.25 \| $220 \| 1.49 [1.42–1.59] \| 79 \| | `ask_used[Ultra 1]` | 1.49, 79 | ✓ |
| Asking vs sold | \| Ultra 2 \| $389.99 \| $315 \| 1.24 [1.17–1.31] \| 63 \| | `ask_used[Ultra 2]` | 1.24, 63 | ✓ |
| Asking vs sold | \| Ultra 3 \| $512.50 \| $480.99 \| 1.07 [1.01–1.10] \| 37 \| | `ask_used[Ultra 3]` | 1.07, 37 | ✓ |
| Asking vs sold | \| Series 9 \| $200 \| $130 \| | `ask_used[Series 9]` | $200, $130 | ✓ |
| Asking vs sold | \| Ultra 3 \| $512.50 \| $480.99 \| | `ask_used[Ultra 3]` | $512.50, $480.99 | ✓ |
| Asking vs sold | Every interval is above 1 | `min(ask_used.ratio_lo)` | see source | ✓ |
| Asking vs sold | (Series 9 1.51×, Ultra 3 1.16×) | `ask_new` | 1.51, 1.16 | ✓ |
| Part I bridge | The Series 2, 4 and 3 averaged $664–743 in Part I, with 42–88% of their listings gold-plated | `bridge.part1_mean_ask / part1_gold_share` | 664, 743, 42, 88% | ✓ |
| Part I bridge | On eBay they sell for a median of **$49.99, $49.99 and $35** | `bridge.part2_median_sold` | $49.99, $49.99, $35 | ✓ |
| Part I bridge | The Ultra 3, Part I's 4th-ranked model at $651, sells for $499.99, the highest median sale of any model in the comparison | `bridge` | $651, $499.99 | ✓ |
| Time to sale | Listings that ended without a confirmed outcome (247) | `survival.ended_unknown` | 247 | ✓ |
| Time to sale | \| Below 90% \| 337 \| 28% \| 41% [35–47] \| 47% \| | `survival.table[Below 90%]` | see source | ✓ |
| Time to sale | \| 90–110% \| 714 \| 17% \| 30% [26–34] \| 39% \| | `survival.table[90–110%]` | see source | ✓ |
| Time to sale | \| 110–150% \| 761 \| 6% \| 13% [11–16] \| 17% \| | `survival.table[110–150%]` | see source | ✓ |
| Time to sale | \| Above 150% \| 500 \| 3% \| 7% [5–10] \| 8% \| | `survival.table[Above 150%]` | see source | ✓ |
| Time to sale | Across all 2,312 listings, 21% were sold by 72 hours | `survival.n / sold_72h` | 2,312, 21% | ✓ |
| Repricing | among 26,571 fixed-price watch listings observed more than once, only **9.8%** changed price during the week, and 7.6% ended lower than they started (median cut −5.7%) | `repricing` | 26,571, 9.8%, 7.6%, −5.7 | ✓ |
| Gold | The collector found **299** listings with 24k gold: 292 gold-plated watches, 5 anodized watches with 24k parts, 1 band and 1 plating service | `gold.kinds` | 292, 5 | ✓ |
| Gold | Their median ask is **$1,199** (IQR $881–1,699; range $199–4,749) | `gold.median_ask / ask_q1 / ask_q3 / min_ask / max_ask` | $881, 1,699, $199, 4,749 | ✓ |
| Gold | For the 286 plated watches with an identified model, the median ask is **8.2×** the median ask for the same model and **13.5×** its median sale price, from 6× for an Ultra 4 to 22× for a Series 3 | `gold.plated_n / median_ask_ratio / median_sold_ratio / by_model` | 286, 8.2, 13.5, 6×, 22× | ✓ |
| Gold | all 299 are fixed-price, good-'til-cancelled listings (290 with Best Offer) | `gold.gtc_share / formats` | 290 | ✓ |
| Gold | the median listing has been up for **4.1 years** (IQR 2.5–6.1), and 82% for more than two years; other active fixed-price watches have been up for a median of 7 months | `gold.median_age_years / age_q1 / age_q3 / share_older_2y; images/07` | 2.5, 6.1, 82% | ✓ |
| Gold | **10 sellers** list them, the largest 216 (72%), and the top three 95% | `gold.n_sellers / top_seller / top_seller_share / top3_share` | 10, 216, 72%, 95% | ✓ |
| Gold | most are New (163) or Open box (129) | `gold.conditions` | 163, 129 | ✓ |
| Gold | Those sold at **1.07%** during the week (n = 1,777). At that rate, the 286 plated watches would be expected to produce 3.1 sales, and the chance of seeing none is **0.046**. But comparable standard listings priced at $500 or more sold **0 of 566** | `gold.window_*` | 1.07%, 1,777, 3.1, 0.046, 0 of 566 | ✓ |
| Gold | Among the 297 gold listings with full details, 45% have never sold a unit; together they have sold 481 units, a median of **0.15 per listing per year**. A quarter (26%) offer more than one unit | `gold.lifetime_* / multi_qty_share` | 297, 45%, 481, 0.15, 26% | ✓ |
| Auctions | Of **724** ended single-watch auctions, **373 sold (51.5%; 95% CI 47.9–55.1%)** | `auctions.n / k / rate / ci` | 724, 373, 51.5%, 47.9–55.1 | ✓ |
| Auctions | Series 9 and 10 auctions sold 63% of the time (63/100) against 36% for the Series 3 (26/73), a difference of 27 points (95% CI 12–41; p = 0.0004) | `auctions.new_vs_s3` | 63/100, 26/73, 27 points, 12–41, 0.0004 | ✓ |
| Auctions | Sellers with 10,000+ feedback sold 69% of their auctions; sellers with zero or negative feedback, 28% (trend p = 0.0002) | `auctions.by_feedback / feedback_trend` | 69%, 28%, 0.0002 | ✓ |
| Auctions | Free-shipping auctions sold more often (62% vs 50%, p = 0.023) | `auctions.free_shipping` | 62%, 50%, 0.023 | ✓ |
| Auctions | A logistic regression with condition and model family controls (n = 723) | `auctions.adjusted_n` | 723 | ✓ |
| Auctions | odds ratio **1.24 [1.10–1.40]** per tenfold increase in seller feedback (p = 0.0006) | `auctions.adjusted.log_fb` | 1.24, 1.10, 1.40, 0.0006 | ✓ |
| Auctions | **1.76 [1.24–2.51]** for current-generation models (p = 0.002) | `auctions.adjusted.new_gen` | 1.76, 1.24, 2.51, 0.002 | ✓ |
| Auctions | **1.11 [0.69–1.78]** for free shipping (p = 0.68) | `auctions.adjusted.free` | 1.11, 0.69, 1.78, 0.68 | ✓ |
| Auctions | 54.8% of free-shipping and 56.3% of paid-shipping listings that ended recorded a sale (p = 0.43) | `fixed.free_shipping` | 54.8%, 56.3%, 0.43 | ✓ |
| Auctions | Auctions still showing Best Offer at the end sold 4.1% of the time, against 63.5% for the rest | `auctions.leak_best_offer` | 4.1%, 63.5% | ✓ |
| Trajectories | The median auction stood at 62% of its final price more than three days out, **76% at 24–48 hours**, 90% at 1–3 hours and 97% in the last 15 minutes | `trajectories.table` | 62%, 76%, 90%, 97% | ✓ |
| Trajectories | 59% of auctions still rose, by a median of **3.3%** (95% CI 1.6–6.2%; n = 197). A sold auction received a median of 10 bids | `trajectories.late_*` | 59%, 3.3%, 1.6–6.2, 197, 10 | ✓ |
| Sale model | **Sample:** 525 ended auctions first observed before their first bid, so the opening price is known. 185 of them sold (35%), from 387 sellers | `sale_model.metrics` | 525, 185, 35%, 387 | ✓ |
| Sale model | the 199 auctions that already had bids when first seen, 94% of which sold | `data/public: ended auctions with first_bid_count > 0` | 199, 94% | ✓ |
| Sale model | the out-of-fold AUC is **0.69 [0.65–0.73]** (fold range 0.63–0.76), against 0.59 [0.54–0.64] for a logistic regression | `sale_model.metrics.auc*` | 0.69, 0.65–0.73, 0.63–0.76, 0.59, 0.54–0.64 | ✓ |
| Sale model | the Brier score is 0.216, against 0.228 for always predicting the base rate | `sale_model.metrics.brier / brier_base` | 0.216, 0.228 | ✓ |
| Sale model | the slope is 0.65 | `sale_model.metrics.calibration.slope` | 0.65 | ✓ |
| Sale model | Its highest-probability fifth predicted 70% and sold 55% | `sale_model.reliability[4]` | 70%, 55% | ✓ |
| Sale model | (mean \|SHAP\| 0.41 log-odds), ahead of seller feedback (0.26), model (0.13) and auction length (0.10) | `sale_model.importance` | 0.41, 0.26, 0.13, 0.10 | ✓ |
| Sale model | falls from **48%** for an opening bid at a quarter of the market price to **36%** at the market price, **27%** at 1.5× and **21%** at 3× | `sale_model.partial` | 48%, 36%, 27%, 21% | ✓ |
| Price model | **Sample:** 1,873 sold single watches from 1,196 sellers | `price_model.metrics.n / sellers` | 1,873, 1,196 | ✓ |
| Price model | the out-of-fold **R² is 0.90**, with a mean absolute error of $28.18 and a median absolute percentage error of 14.7% | `price_model.metrics` | 0.90, $28.18, 14.7% | ✓ |
| Price model | reaches R² = 0.87 and $28.99 | `price_model.metrics.r2_base / mae_base` | 0.87, $28.99 | ✓ |
| Price model | the model ($53.15), condition ($30.47), case material ($19.72), case size ($16.28) and titanium ($11.47) dominate | `price_model.importance` | $53.15, $30.47, $19.72, $16.28, $11.47 | ✓ |
| Price model | Format comes next ($4.75). Seller feedback ($2.48), shipping cost ($1.16) and free shipping ($0.84) | `price_model.importance` | $4.75, $2.48, $1.16, $0.84 | ✓ |
| Price model | averages **−$13.79** (n = 307), against +$3.72 for fixed price (n = 886) and +$2.02 for fixed price with Best Offer (n = 680) | `price_model.format_shap` | 13.79, 307, 3.72, 886, 2.02, 680 | ✓ |
| Price model | Each prediction starts from the average sale ($172.44) | `price_model.expected` | $172.44 | ✓ |
| Price model | A typical used Series 9 sold for $130 and is predicted at $130.46. Used condition (−$16.64), aluminum case (−$11.62) and the 41 mm size (−$9.71) | `images/16 (scripts/make_figures.py example_index)` | see source | ✓ |
| Price model | A used Ultra 2 sold for $315 and is predicted at $311.46. Titanium shows up in material (+$48.72) and titanium (+$30.01), next to the model (+$45.17) and the 49 mm case (+$27.96) | `images/17 (scripts/make_figures.py example_index)` | see source | ✓ |
| Collection | pages through the whole category in 17 price bands | `collector/config.py DEFAULT_PRICE_BANDS` | 17 | ✓ |
| Collection | auctions ending within 45 minutes | `collector/config.py ending_soon_window_minutes` | 45 | ✓ |
| Collection | up to 60 full item records per tick | `collector/config.py detail_batch_per_tick` | 60 | ✓ |
| Collection | eBay allows 5,000 calls per day. The collector kept a 5% safety margin, held 1,200 calls in reserve for end checks | `collector/config.py` | 5,000, 5%, 1,200 | ✓ |
| Gold | other active fixed-price watches have been up for a median of 7 months | `data/public: active non-gold fixed-price watches, median age` | 7 months | ✓ |
| Collection | 7 sweeps saw 24,992–26,637 items each | `overview.sweeps / sweep_items_min / max` | 7, 24,992, 26,637 | ✓ |
| Collection | \| Sold \| auction ended with bids, or fixed-price `sold_quantity` rose without Best Offer \| high \| 1,327 \| | `overview.outcomes_by` | 1,327 | ✓ |
| Collection | \| Sold \| fixed-price sale while Best Offer was on (price paid unknown) \| medium \| 734 \| | `overview.outcomes_by` | 734 | ✓ |
| Collection | (Buy It Now or offer) \| medium \| 2 \| | `overview.bin_sales_reclassified` | 2 | ✓ |
| Collection | \| Unsold \| auction ended with no bids \| high \| 385 \| | `overview.outcome_counts.unsold` | 385 | ✓ |
| Collection | \| Reserve not met \| auction ended with bids below the reserve \| high \| 9 \| | `overview.outcome_counts.reserve_not_met` | 9 | ✓ |
| Collection | \| Ended, outcome unknown \| ended or disappeared with no sale signal \| low \| 1,386 \| | `overview.outcome_counts.ended_unknown` | 1,386 | ✓ |
| Collection | In total it made **20,399** calls (18,020 item reads, 2,375 searches): 20,205 succeeded and 130 returned 404 | `overview.api_calls / api_calls_by_kind / api_status` | 20,399, 18,020, 2,375, 20,205, 130 | ✓ |
| Collection | for 51.1 of the 168.2 hours (69.6% coverage) | `overview.gap_hours / window_hours / covered_share` | 51.1, 168.2, 69.6% | ✓ |
| Collection | Full details were fetched for 30.6% of listings; 59.3% have no brand field | `overview.detail_share / brand_missing_share` | 30.6%, 59.3% | ✓ |
| Collection | The analysis set keeps 28,214 single watches | `overview.analysis_listings` | 28,214 | ✓ |
| Collection | 632 multi-watch lots, 343 accessories and 116 other items | `overview.lots / accessories / other` | 632, 343, 116 | ✓ |
| Collection | 1,130 watches with no identifiable model | `overview.no_model` | 1,130 | ✓ |
| Collection | 868 robust price outliers | `overview.price_outliers` | 868 | ✓ |
| Collection | Formats: 18,991 fixed price with Best Offer, 10,910 fixed price, 1,597 auctions | `overview.format_counts` | 18,991, 10,910, 1,597 | ✓ |
| Collection | \| Mon Oct 19, 12:25 PM – 3:00 PM \| 2.6 \| | `data/public/collection_gaps.csv (UTC → MT)` | Mon Oct 19, 12:25 PM – 3:00 PM, 2.6 | ✓ |
| Collection | \| Mon Oct 19, 6:10 PM – Tue Oct 20, 7:27 AM \| 13.3 \| | `data/public/collection_gaps.csv (UTC → MT)` | Mon Oct 19, 6:10 PM – Tue Oct 20, 7:27 AM, 13.3 | ✓ |
| Collection | \| Tue Oct 20, 9:41 PM – Thu Oct 22, 8:54 AM \| 35.2 \| | `data/public/collection_gaps.csv (UTC → MT)` | Tue Oct 20, 9:41 PM – Thu Oct 22, 8:54 AM, 35.2 | ✓ |
| Limitations | 734 sales were made while Best Offer was on | `overview.outcomes_by` | 734 | ✓ |
| Limitations | 1,386 listings ended with no confirmed outcome | `overview.outcome_counts.ended_unknown` | 1,386 | ✓ |

Collection settings come from `collector/config.py`. The two SHAP examples are computed in `scripts/make_figures.py` and shown in images 16 and 17; `notebooks/01_from_asking_to_selling.ipynb` reproduces the Series 9 example.
