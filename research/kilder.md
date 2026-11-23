# Datakartlegging 19. november 2026

Laget med fem uavhengige søk og én kontrollagent. Grunnlaget ligger i `datakartlegging_2026-11-19.json`. Merket **sjekket** betyr at kilden ble åpnet og talt opp. **Sjekket to ganger** betyr at den også ble kontrollert uavhengig etterpå.

## Svaret kort

- **Storbritannia:** det finnes ingen åpne reservetall per felt og år. NSTA og DECC publiserer bare totaler for hele sektoren, og operatørenes tall per felt er fortrolige (UKCS Stewardship Survey).
- **Norge:** Sodir har nøyaktig det oppgaven trenger, fra 2004 til 2025.

## Norge (Sodir FactPages, NLOD 2.0)

| Tabell | Innhold | Status |
|---|---|---|
| `field_reserves` | Ett anslag per felt for hvert ressursregnskap (`fldVersion` 2004–2025). 2 333 rader og 145 felt, som øker fra 66 felt i 2004 til 141 i 2025. Kolonner: fldRecoverableOil/Gas/NGL/Condensate/OE, fldRemaining*, fldDateOffResEstDisplay, fldNpdidField | **sjekket to ganger** (Grane olje: 120,31 i 2004 og 150,78 MSm³ i 2025) |
| `field_production_monthly` | Produksjon per felt, 1971–2026, 136 felt | sjekket |
| `field_activity_status_hst` | Statushistorikk med produksjonsstart. 74 felt startet i 2004 eller senere og har reserverader. | sjekket |
| `field_in_place_volumes` | Tilstedeværende volum, bare øyeblikksbilde per 31.12.2025 | sjekket |
| Gamle NPD-årsrapporter før 2004 | Kanskje reserver per felt | ikke sjekket, bare fra hukommelsen |

## Storbritannia

| Kilde | Innhold | Status |
|---|---|---|
| NSTA PPRS FeatureServer | Månedlig produksjon, 419 rapporteringsenheter, 1975-06 til 2026-08, 109 185 rader, ingen reserver | **sjekket to ganger** |
| NSTA Offshore hydrocarbon fields | 471 felt med oppdagelsesdato, oppstartsdato, type, havdyp og operatør. Ingen reserver. | sjekket |
| NSTA Reserves and Resources-rapporter (2016–) og DECC "UK Oil Reserves and EUR" | Bare totaler for sektoren. Rapportene skriver selv at feltenes tall er summert. | sjekket |
| Brown Book-sidene per felt (Wayback, `og.decc.gov.uk/information/bb_updates/appendices/fields/*.htm`) | «Operator's estimate of recoverable reserves originally present» for cirka 250 felt. Ett øyeblikksbilde fra cirka 2001 (Alba: 61,40 Mt, start 1994). | **sjekket to ganger** |
| Brown Book, vedlegg 9/10 (Wayback) | Produksjon per felt 1975–2008 | sjekket |
| Brown Book, papirutgaver fra 1970-tallet til 2001 | Ville gitt reserver per felt år for år, men finnes ikke åpent (HathiTrust kan bare søkes i, Internet Archive bare lånes) | ikke tilgjengelig |
| Geological Society Memoir 14 (1991), 20 (2003) og 52 (2020) | Øyeblikksbilder for cirka 70–150 felt, mest bak betalingsmur | søkeutdrag |
| De britiske NDR-rapportene på Linux-PC-en (`text_corpus/`) | 1 631 PDF-er, nesten bare brønnrapporter. Under 15 dokumenter har et reelt reserveanslag for et felt. | sjekket, ikke nyttig |

## Litteratur

- **Watkins, G.C. (2000).** MIT CEEPR WP 00-008, publisert i 2002 i Quarterly Review of Economics and Finance 42(2):335–372. Tabell D-1 og D-2 gir initiale reserver og 1996-reserver for 96 britiske og 30 norske oljefelt. Vekstfaktoren er 1,22 for Storbritannia og 1,47 for Norge, og han fant ingen typisk kurve for hvordan et felt utvikler seg. **Sjekket to ganger** (Piper 636 → 1017 mmbbl). https://ceepr.mit.edu/wp-content/uploads/2023/02/2000-008.pdf
- **Sem & Ellerman (1999).** MIT CEEPR WP 99-011. Bare metadata er sjekket.
- **Klett & Gautier (2005).** Petroleum Geoscience 11:179–190, om reservevekst i Nordsjøen. Bare sammendraget er sjekket.
- **Gautier, Klett & Pierce (2005).** USGS OFR 2005-1355 (lysbilder). Sjekket.
- **Thompson, Sorrell & Speirs (2009).** UKERC TR3, om reservevekst. Sjekket.
- **Dromgoole & Speers (1997).** Geoscore, Petroleum Geoscience 3:1–12. Fant at enkle britiske felt ble undervurdert med cirka 20 %, og komplekse overvurdert med 10–15 %. **Bare søkeutdrag.**
- **NPD (2015).** Evaluation of reserve growth for oil 2005–2014. Sjekket. https://www.sodir.no/globalassets/1-sodir/publikasjoner/rapporter-en/evaluation-of-reserve-growth.pdf
- **Wittemann / GEO ExPro (2021).** Small fields tend to be overestimated. Gjelder 40 norske felt som startet i 2010–2020. Sjekket. https://geoexpro.com/the-size-of-small-fields-tends-to-be-overestimated/

## Ikke sjekket

- Lisenssidene for NSTA og gov.uk (OGL) og for Sodir (NLOD).
- Om gamle NPD-publikasjoner har reserver per felt før 2004.

## Tillegg 19. november 2026: lisenser og nye funn (sjekket under gjennomføringen)

- **Sodir:** Siden https://www.sodir.no/en/facts/data-and-analyses/open-data/ sier at data publiseres under «Norwegian Licence for Open Government Data (NLOD)». Versjonsnummeret står ikke i teksten vi leste. **Sjekket.**
- **NSTA:** Laget «Offshore hydrocarbon fields» er merket «NSTA Open User Licence» i metadataene. PPRS-laget har tomt lisensfelt. Det er altså ikke bekreftet at dette er OGL v3. Selve lisensteksten er ikke lest. **Metadata sjekket.**
- **Brown Book-sidene:** 250 feltsider er hentet fra Wayback (opptak fra 2009). 240 av dem oppgir lisensandeler «at end of February 2002». Sidene oppgir ingen lisens. **Sjekket.**
- **PPRS mangler felt:** Flere eldre britiske felt har ingen rader i PPRS-tjenesten, blant annet Dunlin, Miller, Beatrice, Hutton og Buchan. Summen i PPRS ligger også under kjent britisk oljeproduksjon i toppårene. **Sjekket** ved opptelling av feltnavn.
- **Sodir-varsel 26.02.2026:** Feltenes reservetall per 31.12.2025 ble først publisert med feil i gjenværende reserver. Nedlastingen vår fra 19.11.2026 har 2025-tall for alle felt unntatt Frøy og Lille-Frigg. **Sjekket** på sodir.no.
- **Antall felt:** Tabellen har 145 feltnavn, men 142 felt med anslag over null. «JOTUN » står én gang med mellomrom, og Vega Sør og Ærfugl finnes ikke i felttabellen.

## Tillegg 2, 19. november 2026: andre gjennomgang (nye kilder)

- **Brown Book, nettutgavene 1998–2001:** Funnet i Wayback under `dbd-data.co.uk/bb1998/`, `bb1999/`, `bb2000/` (også som `bbonline/`) og `bb2001/`. Hver utgave har én side per felt med operatørens anslag for «recoverable reserves originally present» og lisensandeler «at end of 1997», 1998, 1999 og 2000. **Sjekket** på Alba (50,72 → 50,72 → 61,40 → 61,40 millioner tonn) og Forties (336,46 → 344,51 → 345,29 → 347,42).
- **2002-oppdateringen gjentar 2001-tallene:** Sidene under `bb_updates` (lisensandeler per februar 2002) har samme reservetall som 2001-utgaven for 145 av 145 sammenlignede felt. Den britiske serien slutter derfor med anslaget per utgangen av 2000. **Sjekket.**
- **Retting av første kartlegging:** «Det finnes ingen åpne reservetall per felt og år for Storbritannia» var for sterkt. Riktig er: åpent for fire årsskifter (1997–2000), pluss oppstart og 1996 fra Watkins. Etter 2000 finnes ingenting per felt.
- **Vedlegg 3 (1998–1999) og 5 (2000–2001), «Significant offshore discoveries»:** Reservoaralder, område og hydrokarbontype per britisk felt. Lastet ned, men ikke brukt i analysen.
- **Sodirs brønntabeller** (`wellbore_exploration_all`, `wellbore_development_all`): Brukt til å telle lete- og avgrensningsbrønner før oppstart og produksjons- og injeksjonsbrønner per felt. **Sjekket** på Oselvar (4 letebrønner, 3 produksjonsbrønner) og Vega.
- **Nettarkivet struper raske klienter:** Én forespørsel per sekund ga «connection refused». Én per 4 sekunder fungerer.
