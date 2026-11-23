# Manus: Hvor feil er de første reserveanslagene?

FORCE VibeCode Hackathon, fredag 20. november 2026 kl. 13.30. Maks 4 minutter, cirka 410 ord i selve manuset.
Alle tall står i `web/data/*.json` og vises på nettsiden. `python pipeline/key_numbers.py` skriver dem ut samlet.
Hvis tiden blir knapp: kutt lysbilde 5.

---

**[Lysbilde 1 – problemet]**

Når et felt settes i produksjon, har operatøren et anslag på hvor mye olje og gass det vil gi totalt. Det tallet styrer investeringer på titalls milliarder kroner. Men det er et anslag, ikke en måling, og det regnes på nytt hvert år. Vi spurte: Hvor mye endrer det seg, og hva kjennetegner feltene som bommer mest?

**[Lysbilde 2 – data]**

Ideen kom fra en geolog i Equinor, som spurte om britisk sektor. Der publiserer myndighetene i dag bare totaler. Men i nettarkivet fant vi fire årganger av den britiske «Brown Book», med operatørens anslag for hvert felt fra 1997 til 2000. Norge publiserer hele tabellen: ett anslag per felt for hvert år fra 2004 til 2025, for 142 felt. Hovedanalysen er derfor norsk, og Storbritannia er en kryssjekk.

**[Lysbilde 3 – funn 1: hvor mye]**

Først: Hvor mye bommer anslagene? Vi fulgte 55 norske felt fra det siste anslaget før oppstart. Tre år senere ligger medianfeltet 9 prosent lavere. Men spredningen er det viktige: 31 av de 55 er justert mer enn 20 prosent ned eller 25 prosent opp. Oselvar mistet 84 prosent på tre år. Vega ble nesten tredoblet.

**[Lysbilde 4 – funn 2: tre kjennetegn]**

Så det vanskelige spørsmålet: Hva kjennetegner feltene som endrer seg mye? Vi fant tre ting.

Én: De er små. Felt under 100 millioner fat er typisk justert 44 prosent etter tre år, større felt 19 prosent. Nesten alle de små er satellitter knyttet til en annen innretning. Det samme mønsteret finnes i 109 eldre britiske og norske felt.

To: Nedjusteringene kommer fort. Feltene som endte kraftig ned, hadde tre firedeler av tapet i tallene etter bare ett år. Oppjusteringene kommer sakte: Etter tre år var bare en femdel på plass.

Tre: Oppjusteringene kommer der det bores videre. Felt med nye brønner etter første år vokste 27 prosent. Felt uten vokste 3 prosent.

**[Lysbilde 5 – det som ikke slo ut]**

Like viktig er det som ikke slo ut: olje eller gass, havområde, operatør, vanndyp og antall letebrønner før oppstart. Vi kan si at anslaget for et lite felt er usikkert, men ikke hvilken vei det går.

**[Lysbilde 6 – Storbritannia, begrensninger og neste steg]**

For Storbritannia kan vi sammenligne oppstartsanslaget med det feltet faktisk produserte, for 35 felt som er stengt. Medianfeltet ga 14 prosent mer enn anslått, og den typiske bommen var 28 prosent. I Brown Book ble unge felt justert tre ganger så mye som modne.

Begrensningene er tydelige: 55 nye felt er få, størrelse og utbyggingsløsning lar seg ikke skille, og vi vet ikke hvorfor et anslag ble endret. Neste steg er årsakene bak hver store endring.

Alt bygger på åpne data, og koden ligger åpent. Takk.

---

## Forslag til lysbilder

| # | Tittel på lysbildet | Figur | Én setning under |
|---|---|---|---|
| 1 | Hvor feil er de første reserveanslagene? | Ingen figur. Grane som eksempel: 120,3 → 150,8 millioner Sm³ olje fra 2004 til 2025 (+25 %) | Et reserveanslag er et anslag, ikke en måling |
| 2 | Norge har hele tabellen. Storbritannia har fire år i nettarkivet. | `figures/fig7_uk_estimates_1997_2000.png`, eller en liten tabell: Sodir 142 felt × 22 år, Brown Book 1997–2000 | Hovedanalyse på Norge, Storbritannia som kryssjekk |
| 3 | Tre år etter oppstart er 31 av 55 felt justert kraftig | `figures/fig1_new_fields_from_pre_start_estimate.png` | Median −9 %, 20 felt ned og 11 opp |
| 4 | Små felt endres dobbelt så mye, og nedjusteringene kommer først | `figures/fig3_small_fields_revised_more.png` til venstre, `figures/fig4_downgrades_fast_upgrades_slow.png` til høyre | ±44 % mot ±19 % etter tre år |
| 5 | Vekst følger boring. Felttype, område og operatør slo ikke ut. | `figures/fig5_growth_follows_drilling.png` | +27 % med nye brønner, +3 % uten |
| 6 | Storbritannia: anslag mot faktisk produksjon | `figures/fig6_uk_startup_estimate_vs_outcome.png` | 35 stengte felt: median +14 %, typisk bom 28 % |

Vis gjerne nettsiden direkte på lysbilde 3: hold musen over en linje, og klikk på Oselvar eller Vega.

## Tall å ha i bakhånd ved spørsmål

- **To måter å måle på.** Fra anslaget før oppstart er medianen −8 % etter ett år, −9 % etter tre og −13 % etter fem. Fra anslaget ved utgangen av oppstartsåret er medianen ±0 etter tre år og −1 % etter fem. Forskjellen er at 13 felt ble justert mer enn 20 % allerede i oppstartsåret, og det ser man ikke hvis klokka starter etterpå.
- **Volumveid** er de 55 feltene på −4 % etter tre år og −1 % etter fem. De store feltene holder.
- **Størrelse:** Forholdet er 2,1 (90 %-intervall 1,2–4,6), p = 0,03. Forskjellen oppstår i oppstartsåret og år 1 (±26 % mot ±8 %). Fra år 1 til år 5 endres små og store felt like mye (±17 % mot ±16 %). Med grensen på 200 eller 300 millioner fat er p = 0,004 og 0,002.
- **Retning:** Små felt ligger på −18 % i median etter tre år, større på +1 %, men den forskjellen er ikke statistisk klar (p = 0,13).
- **35 av 37 små felt er satellitter**, mot 3 av 18 større. Størrelse og utbyggingsløsning kan derfor ikke skilles.
- **Watkins:** I 109 felt med oppstart 1971–1995 øker justeringen når feltet er mindre (p = 0,004; bare britiske felt: p = 0,006).
- **Tid:** Av 13 felt som endte minst 20 % ned, hadde 69 % nådd halve tapet etter ett år. Av 15 felt som endte minst 25 % opp, hadde ingen nådd halve gevinsten etter ett år, og 20 % etter tre.
- **Tommelfingerregel:** Av 31 felt som ikke var nedjustert 20 % tre år etter oppstart, endte bare ett (Enoch) så lavt, og 14 endte minst 25 % opp. Av 17 felt som var nede 20 % etter tre år, var 12 fortsatt nede i siste anslag.
- **Boring, eldre felt:** Blant 38 eldre felt som fortsatt produserer, vokste tredelen som boret mest, +41 %, og tredelen som boret minst, +12 %. Men små eldre felt vokste mest i prosent, så med størrelse holdt fast er sammenhengen ikke klar (p = 0,23).
- **Modell:** Med bare størrelse og utbyggingsløsning treffer en kryssvalidert modell litt bedre enn tilfeldig (AUC 0,64, p = 0,04). I første runde, med klokka startet etter oppstartsåret, var den 0,46.
- **Ikke støttet:** Flere lete- og avgrensningsbrønner per fat ga ikke mindre justering. Dype reservoarer heller ned etter tre år (p = 0,04), men ikke etter fem.
- **Eldre felt:** De 59 feltene som produserte før 2004, har vokst 17 % samlet. 28 oljefelt fulgt fra oppstart via Watkins er doblet (×1,99).
- **Storbritannia, utfall:** 35 stengte felt, median +14 % (90 %-intervall −5 % til +22 %). 34 % endte minst 25 % over oppstartsanslaget, 17 % minst 20 % under. Her er det ingen forskjell mellom små og store felt (±28 % mot ±27 %).
- **Storbritannia, Brown Book 1997–2000:** Unge felt (i drift tre år eller mindre) ±19 %, modne ±6 % (p < 0,001). Små felt ±15 %, større ±7 % (p = 0,07). 2002-oppdateringen gjentar 2001-tallene (145 av 145 felt like), så serien stopper i 2000.
- **Storbritannia, indikator:** 67 % av 79 oljefelt har produsert mer enn anslaget i 2001-utgaven.
- **Kontroll:** Summen av de norske feltene gir 57,1 % solgt og levert av Sodirs total for 2025. Sodir oppgir cirka 57 %.
