# Reservevekst: hvor feil er de første anslagene?

Hackathonprosjekt (FORCE VibeCode, Stavanger, 19.–20. november 2026). Prosjektet tok utgangspunkt i et spørsmål om britiske reserveanslag. Det er et nytt prosjekt, ved siden av Nature's Plug.

- **Hva som er sjekket av data:** `research/kilder.md`.
- **Rådata:** `raw/`.

## 1. Hva er «reserver»?

Når et oljefelt blir funnet, vet ingen nøyaktig hvor mye olje og gass som kan hentes opp. Det må anslås. Da skiller man mellom to ting:

- **Tilstedeværende volum:** hvor mye som faktisk ligger i bergarten.
- **Reserver:** hvor mye av det som kan produseres lønnsomt. Det er ofte bare 30–50 % av det som ligger der.

Reserver er altså et **anslag, ikke en måling**. Det bygger på seismikk, noen få brønner, laboratorieprøver og datamodeller, og alle disse er usikre.

## 2. Problemet: anslagene endrer seg

Hvert år regner operatøren reservene på nytt. Etter hvert som feltet produserer, lærer man mer. Reservoaret kan være større enn antatt, vannet kan komme raskere inn i brønnene enn ventet, eller ny teknologi kan gjøre at mer kan hentes ut. Et eksempel: Grane var anslått til 120 millioner Sm³ olje i 2004, men til 151 millioner i 2025. Det er 25 % mer enn man trodde. Dette kalles **reservevekst**.

## 3. Spørsmålet

1. Hvordan har anslaget for hvert felt endret seg fra år til år?
2. Hva kjennetegner feltene der anslaget endret seg mye de første årene etter oppstart? Er det små felt, komplekse geologiske felt, gassfelt eller felt med en bestemt bergart?

## 4. Hvorfor det har verdi

En feltutbygging koster ofte 10–50 milliarder kroner. Et oljeselskap er i stor grad verdt reservene sine (Shell måtte nedjustere med omtrent 20 % i 2004). Staten planlegger skatteinntekter ut fra hva som ligger igjen. Hvis man vet hvilke typer felt som systematisk blir feilvurdert, kan anslagene korrigeres tidligere, og det gir bedre milliardbeslutninger.

## 5. Hva som allerede er kjent

- En studie fra MIT i 2000 (Watkins) fant at britiske felt i snitt vokste 22 % fra oppstart og norske 47 %, og at det ikke finnes noen typisk kurve.
- En artikkel fra 2021 fant at små norske felt ofte blir kraftig nedjustert.

Etter rundt 2009 har nesten ingen gjort en systematisk analyse felt for felt.

## 6. Data

- **Storbritannia:** bare totaler for hele sektoren er åpne. Tallene per felt er fortrolige.
- **Norge:** Sodir publiserer et anslag per felt for hvert år fra 2004 til 2025, for 145 felt, i tillegg til produksjon og oppstartsår.

Hovedanalysen gjøres derfor på Norge, med Storbritannia som kryssjekk.

*Rettet 19. november 2026: Fire årganger av den britiske Brown Book (1998–2001) med operatørens anslag per felt finnes i nettarkivet. Britiske tall per felt er altså åpne for årsskiftene 1997–2000. Se `README.md`. Antallet norske felt med anslag er 142.*

**Med én setning:** vi undersøker hvor feil de første anslagene for norske oljefelt pleier å være, og hvilke felt som er mest feil.
