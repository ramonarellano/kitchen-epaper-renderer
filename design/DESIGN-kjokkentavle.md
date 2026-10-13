# Kjøkkentavla – designspesifikasjon (v8)

Kjøkkentavla er en håndtegnet familietavle for **Waveshare 7.3" 7-farge e-papir (7.3F)**, 800 × 480 piksler i liggende format.

- **Implementasjon (fasit):** `main.py` (oppsett og tekst), `sketch.py` (håndtegnede streker, værikoner, små ikoner) og `seasonal.py` (temaer, merkedager, nedtelling og sesongscene). Ved uenighet mellom dette dokumentet og koden er det koden som gjelder. Oppdater dokumentet når koden endres.
- **Prototype:** `kjokkentavle-konsept.html` (én SVG tegnet med rough.js og skriften Kalam). Den viser oppsettet med eksempeldata, men har ikke alle plassreglene. Se avsnitt 10.
- **Referansebilder** (tegnet av den ekte koden med eksempeldata): `kjokkentavle-v8-host.png`, `kjokkentavle-v8-jul.png` og `kjokkentavle-v8-travel.png`.

### Endringer siden v7
- Hodet er lavere: dato 32 px (var 36) og temperatur 36 px (var 40). Innholdet under starter på y=98 (var 108), og sesongfeltet blir 10 px høyere.
- Været viser «Været i morgen» fra kl. 16, fordi met.no ikke har data for timer som har passert. Felt uten data viser en kort strek.
- «I morgen»-tittelen utelates når det ikke er noen hendelser i morgen.
- Nytt personmerke **A** (Alle, hele familien) i svart.
- «og» mellom initialer i prefikset («R og S: Tusenfryd») gir merker for begge.
- Rester av skilletegn etter at navn er fjernet, strykes («Ramon og Solveig: Tog» → (R)(S) Tog). Ordkutt slutter ikke på småord som «i», «på» eller «med».
- Svært travle dager har ett trinn til i plassregelen: dagens hendelser vises også kommaseparert. Se 4.2.
- Personen «M» fra v5 er fjernet.

## 1. Prinsipper

- **Lesbart fra andre siden av kjøkkenet.** All tekst er minst 22 px. Eneste unntak er bokstaven i små personmerker (18 px). Tidspunkt for siste oppdatering vises ikke.
- **Lite tekst.** Hendelser vises med korte titler. Familiemedlemmer vises som fargede merker, ikke som navn.
- **Alle hendelser i dag og i morgen vises alltid.** Antall dager etter i morgen (0–3) tilpasses plassen som er igjen. En dag vises enten med alle hendelser eller ikke i det hele tatt.
- Teksten er svart på hvitt. Farger brukes bare på figurer, personmerker og markeringer. Unntaket er nedbørstallet i værfeltene, som er blått.
- Tegningene har et fast felt som alltid er ledig.

## 2. Panel og rendering

| Punkt | Krav |
|---|---|
| Oppløsning | 800 × 480, liggende. Tegnes rett vei og roteres 180° først i sendesteget (`pil_to_waveshare_7in3f_raw`), fordi panelet er montert opp ned. |
| Palett (indeks) | 0 svart `#000000`, 1 hvit `#FFFFFF`, 2 grønn `#00FF00`, 3 blå `#0000FF`, 4 rød `#FF0000`, 5 gul `#FFFF00`, 6 oransje `#FF8000` |
| Farger | Bare de sju rene fargene. Ingen gråtoner, ingen gjennomsiktighet og ingen dithering. |
| Tegnemetode | Alt tegnes i dobbel oppløsning på to lag. **Blekklaget** er gråtoner for svart tekst og strek; det skaleres ned og terskles (< 150 blir svart), slik at det aldri blir fargede kanter rundt tekst. **Fargelaget** har bare flate fyll i eksakte palettfarger og skaleres ned uten utjevning. Resultatet inneholder bare palettfarger og trenger ingen egen kvantisering. |
| Sending | ESP32 henter `?format=raw`: 4 bit per piksel, to piksler per byte, høyeste halvbyte først, 192 000 byte. |
| Streker | Minst 1,5 px. |
| Gjenskygge | Skjelvingen i strekene og plasseringen av figurer bruker en fast seed per dato. Samme data samme dag gir et piksel-identisk bilde. |

## 3. Typografi (Kalam 400/700)

| Element | px | Vekt |
|---|---|---|
| Temperatur nå | 36 | 700 |
| Nedtelling («19 dager») | 34 | 700 |
| Dato | 32 | 700 |
| Temperatur i værfeltene | 30 | 700 |
| Hendelsestittel (i dag, i morgen) | 29 | 400 |
| Seksjonstittel («I morgen») | 28 | 700 |
| Hendelser de neste tre dagene (kommaseparert) | 27 | 400 |
| Klokkeslett, ukedag og «til D/M» | 26 | 700 |
| Tittel på pågående hendelser | 26 | 400 |
| «Været i dag» / «Været i morgen» | 24 | 700 |
| Etiketter (klokkeslett i værfeltene, vind, nedbør, «til Halloween») | 22 | 400 / 700 |
| Bokstav i personmerke | 21 (18 på de neste dagene) | 700 |

Bare linjene for de neste dagene (og kompakte lister, se 4.2) brytes. All annen tekst kortes, se avsnitt 5.

## 4. Oppsett

```
┌~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~┐
│ Mandag 12. oktober ★                              ☾ 6°    │  hode, strek på y≈63
├────────────────────────────────┬─────────────────────────┤
│ ┌ Maria på sykehuset til 18/10 ┐│ Været i dag              │  første grunnlinje y=98
│ 08:30  Barnehagen              │  08    12    16    20    │
│ 17:00 (E) Fotballtrening       │  ☁     ☀     ☀     ☁     │
│ I morgen 🗑                    │  4°    8°    9°    6°    │
│ 18:30 (K)(S) Øvelseskjøring    │ ≋2    ≋3    ≋3    ≋2     │
│ 19:00 (S) Piano                │ - - - - - - - - - - - -  │
│ 19:00  Foreldremøte            │ 🎃 19 dager              │
│ 19:30 (R) Skvåsj               │    til Halloween         │
│ - - - - - - - - - - - - - - -  │                          │
│ ons  Tannlege                  │   sesongscene            │
│ (tor/fre får ikke plass)       │                          │
└~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~┘
   venstre x 26–496              skillestrek x≈510   høyre x 522–776
```

Alle y-verdier under hodet regnes fra `TOP = 98` i `main.py`.

### 4.1 Ramme og hode
- **Ramme: håndtegnet `~.~.~.~`** langs alle fire kanter, fra (11,11) til (789,469). Hver kant deles i like lange enheter på ca. 34 px. Hver enhet er en liten bølge (utslag ±6 px, strek 2,2) fulgt av en fylt prikk (diameter 5,5). Antall enheter rundes slik at mønsteret går opp på hver kant (`Sketch.wave_border`).
- Datoen står til venstre: 32 px, grunnlinje y=47, for eksempel «Mandag 12. oktober». **Hele dagen-ikoner for i dag** (30 px, maks 3) står rett etter datoen, sammen med ikonet for dagens merkedag.
- Til høyre står været nå: ikon (42 px) og temperatur (36 px, grunnlinje y=48), høyrejustert mot x=772. Minusgrader skrives med ekte minustegn (−).
- Håndtegnet strek på y≈63.

### 4.2 Venstre kolonne: agenda
Radhøyden er 33 px. Linjene for de neste dagene er 32 px høye.

1. **Pågående flerdagshendelser** står øverst i en håndtegnet ramme (strek 1,8), én linje per hendelse. Formatet er personmerker + tittel (26) + **«til D/M»** (26, fet), for eksempel «Maria på sykehuset **til 18/10**» eller «(K) i Bergen **til 15/12**».
   - En hendelse regnes som pågående når den har startet før i dag og varer ut i dag eller lenger.
   - Hendelser som starter i dag og varer flere dager, vises også her.
   - Feltet tegnes ikke når det ikke finnes slike hendelser.
2. **Dagens hendelser:** **alle**, uten tittel, fordi det er gitt at de gjelder i dag.
3. **I morgen:** tittel (28, fet) med eventuelle hele dagen-ikoner etter, og deretter **alle** morgendagens hendelser. Tittelen utelates når det verken er hendelser eller hele dagen-ikoner i morgen.
4. Stiplet håndtegnet skillestrek. Den tegnes bare hvis minst én senere dag får plass.
5. **Dagene etter i morgen** (0–3 dager med hendelser, i rekkefølge): ukedag (26, fet) og deretter alle dagens hendelser kommaseparert, uten klokkeslett, med små personmerker. Linjen brytes mellom hendelser og fortsetter innrykket under. Dager som ligger 7 dager eller mer frem i tid, får «D/M» i stedet for ukedag.

**Plassregel:** I dag og i morgen har førsteprioritet og vises alltid komplett. Deretter legges dagene etter i morgen til én om gangen, så lenge **hele** dagen får plass (siste grunnlinje ≤ y=452). Den første dagen som ikke får plass, og alle etter den, utelates. En dag vises aldri halvveis.

**Hvis i dag og i morgen alene ikke får plass** (svært travle dager), brukes det første trinnet som får plass:
1. Normal radhøyde (33 px).
2. Radhøyde 30 px.
3. Radhøyde 30 px, og morgendagens hendelser kommaseparert med klokkeslett («18:30 Øvelseskjøring, 19:00 Piano»), i samme format som de senere dagene.
4. Som trinn 3, og dagens hendelser også kommaseparert.

Hvis heller ikke trinn 4 får plass, kuttes linjene som ville gått under y=452, i stedet for å tegne inn i rammen.

**Hendelsesrad (i dag og i morgen):** `HH:MM` (fet) → personmerker → kort tittel. Bare starttid vises.

**Hele dagen-hendelser** (søppeltømming, merkedager) får ingen egen rad. De vises som ikon: for i dag etter datoen i hodet, for i morgen etter «I morgen». Flerdagshendelser går i feltet for pågående hendelser. Ikonet velges ut fra ord i tittelen:

| Ord i tittelen | Ikon |
|---|---|
| søppel, avfall, papir, plast, glass | søppelbøtte (grønn) |
| tannlege | tann |
| fly, flyplass, Gardermoen, reise | fly (blått) |
| (alt annet) | stjerne (gul) |

### 4.3 Personmerker
- Håndtegnet sirkel i personens farge, med svart forbokstav inni.
- Diameter 29 (strek 3,2) på i dag, i morgen og pågående hendelser. På de neste dagene er diameteren 25 (skala 0,85, bokstav 18 px).
- Flere personer står ved siden av hverandre.

| Navn | Merke | Farge |
|---|---|---|
| Alle (hele familien) | A | svart |
| Kari | K | rød |
| Ramon | R | grønn |
| Solveig | S | blå |
| Emilie | E | oransje |

**Fra kalendertekst til merker** (`short_title()` i `main.py`):
- Et prefiks med initialer blir merker. Initialene kan skilles med `&`, `+`, `,`, `/` eller «og», og prefikset avsluttes med kolon eller mellomrom. «A» kan også skrives «Alle». Eksempler: «S: Piano», «K&R&E: Høsttreff», «R og S: Tusenfryd», «Alle: Pizzakveld».
- Navnene i tabellen (med stor forbokstav, også «Alle») fjernes fra tittelen og blir merker. Et foranstående «med», «hos» eller «og» fjernes samtidig. Eksempler:
  - «Fotballtrening Emilie» → (E) Fotballtrening
  - «K: Øvelseskjøring med Solveig» → (K)(S) Øvelseskjøring
  - «Luciatog Solveig og Emilie» → (S)(E) Luciatog
  - «Ramon og Solveig: Tidlig tog» → (R)(S) Tidlig tog
  - «Middag Alle» → (A) Middag
- Andre navn (f.eks. Maria, Mariana) blir stående i teksten. Det gjør også «alle» med liten forbokstav («Foreldremøte for alle») og bøyde former som «Karis».

### 4.4 Høyre kolonne: været
- Tittelen «Været i dag» (24, fet) står på y=98. Prognosen gjelder **inneværende dag**. Fra kl. 16 vises i stedet **«Været i morgen»** for neste dag.
- **Fire like brede felt** (ca. 63 px): kl. **08, 12, 16 og 20**. Hvert felt har:
  - klokkeslett (22, fet) på y=128
  - ikon (42 px) med topp på y=134
  - temperatur (30, fet) på y=198
  - vind: lite vind-ikon + m/s som tall (22) på y=228
  - nedbør: blå dråpe + mm (22, fet, blå) på y=254, bare når det er nedbør. Summen for de fire timene fra feltets klokkeslett avrundes til hele mm, og under 1 mm vises som «<1».
  - Et felt uten prognose (time som har passert) viser bare klokkeslettet og en kort strek.
- Stiplet skillestrek på y≈266.

Værikonene tegnes i svart med fargeaksenter: gul sol og måne med oransje stråler, og blå regndråper og snøfnugg. De dekker Met.no-symbolene for klarvær, lettskyet, delvis skyet, skyet, tåke, regn, sludd og snø, med og uten byger og torden, i dag- og nattvariant.

### 4.5 Sesongfelt (x 530–776, y 280–462)
- **Nedtelling:** ikon (42 px) + «NN dager» (34, fet), «1 dag» eller «I dag!», og under det «til <høytid>» (22).
- **Scene:** sesongfigurer på en håndtegnet bakkelinje med grønne gresstuster, og noen få dekorfigurer i luften. Figurene må ikke overlappe teksten.
- **Bursdag:** Bursdager er heldagshendelser i familiekalenderen med ordet «bursdag» i tittelen og uten personprefiks («E: Bursdag Sileih» er en invitasjon og blir i agendaen, det samme gjelder fester med klokkeslett). Har noen bursdag i dag, erstattes hele feltet: ballong (46 px) + navnet (34, fet) og under det «har bursdag!» (22). Scenen er fem ballonger i hver sin farge med snorer knyttet til en gave på bakkelinjen, og to små gaver på sidene. Navnet hentes fra tittelen («Thomas Seeberg Torjussen sin bursdag», «Bursdag Ingrid», «Magdalena bursdag 85»). Fullt navn hvis det får plass, ellers fornavn + etternavn, ellers fornavn. To personer: «Tord og / Kari» på to linjer; flere: fornavn kommaseparert over maks to linjer. Morgendagens bursdager vises som ballongikon ved «I morgen»; senere bursdager vises ikke i agendaen. Bursdager fra Google-kontaktene kopieres til familiekalenderen av en månedlig synkronisering.

## 5. Korte titler

Kalendertitler gjøres korte, helst ett til to ord. Rekkefølgen er:
1. Ordliste med overstyringer: `SHORT_TITLES` i `main.py` (f.eks. «Levere i barnehagen» → «Barnehagen»).
2. Familienavn og personprefiks gjøres om til merker (se 4.3). Skilletegn som blir stående igjen først eller sist i tittelen, strykes.
3. Kutt etter « – » og « - ».
4. Kutt ved ordgrense til det passer, men ikke slik at tittelen slutter på et småord (i, på, med, og, om, til, fra, for, hos, av, en, et, ei). Bruk «…» bare som siste utvei, når ett enkelt ord er for langt. Dette gjelder ikke de neste dagene, som brytes over flere linjer i stedet.

## 6. Ikoner og figurer

Alle ikoner og figurer tegnes i koden med skjelvende håndtegnet strek: svart kontur og helfylt i en ren palettfarge. Det brukes ingen bildefiler.
- **Vær** (`sketch.py`): sol, måne, sky, regn, sludd, snø, torden og tåke.
- **Hele dagen** (`sketch.py`): søppelbøtte, stjerne, fly og tann. I tillegg vind-ikon og nedbørsdråpe.
- **Figurer** (`seasonal.py`): blader, fluesopp, eple, gresskar (også med ansikt), spøkelse, grantre, gave, stjerne, snømann, snøfnugg, vott, hjerte, fyrverkeri, påskeegg, kylling, tulipan, blomst, norsk flagg, ballong, sol, jordbær og iskrem.

## 7. Sesongtema og merkedager

Temaet velges ut fra datoen (`theme_key()` i `seasonal.py`). Det første som passer, gjelder:

| Tema | Periode | Scene |
|---|---|---|
| Nyttår | 27. des – 2. jan | fyrverkeri, stjerner |
| Jul | desember | grantre, gaver, snøfnugg |
| Påske | palmesøndag – 2. påskedag | kylling, egg, tulipan |
| 17. mai | 10.–17. mai | flagg, ballonger, iskrem |
| Valentinsdagen | 10.–14. februar | hjerter, blomster |
| Halloween | 24. okt – 1. nov | gresskar med ansikt, spøkelse, blader |
| Vinter | jan–feb og 20.–30. nov | snømann, grantre, snøfnugg |
| Vår | mars–mai | tulipaner, blomster, kylling |
| Sommer | juni–august | jordbær, iskrem, sol |
| Høst | september–november | fluesopp, gresskar, eple, blader |

**Nedtelling** til nærmeste av disse, hvis den er innen 60 dager: morsdag, valentinsdagen, påskeaften, 17. mai, sankthansaften, Halloween, farsdag, julaften og nyttårsaften.

**Merkedager** som gir ikon etter datoen på selve dagen: morsdag og farsdag (hjerte), valentinsdagen (hjerte), påskeaften og påskedagene (egg), 17. mai (flagg), sankthansaften (sol), Halloween (gresskar), Luciadagen og juledagene (stjerne) og nyttårsaften (fyrverkeri). Listen finnes i `special_days()`.

## 8. Datamodell

Rendereren får rådata og gjør selv om navn og prefiks til merker:

```python
events = [  # fra Google Calendar
    # (dato, start, slutt, tittel); heldagshendelser har bare dato, og slutt er eksklusiv
    ('2026-10-10', '2026-10-10', '2026-10-19', 'Maria på sykehuset'),
    ('2026-10-12', '2026-10-12T17:00:00+02:00', '2026-10-12T18:30:00+02:00', 'Fotballtrening Emilie'),
]
weather = {  # fra met.no, i norsk tid
    'now': {'time': ..., 'date': ..., 'hour': 21, 'temp': 6.1, 'wind': 2.0, 'precip': 0.0, 'icon': 'clearsky_night'},
    'hours': [ ... ],  # samme format, én per time i dag og i morgen
}
```

## 9. Testsjekkliste

Automatisert i `tests/test_epaper.py`. `./deploy.sh` kjører testene og deployer bare hvis alle består:
- Hele endepunktet (PNG, raw og JPEG) med falsk kalender og falsk met.no: riktig størrelse, bare palettfarger, gyldig raw-ramme.
- Alle temaer gjennom året, tidlig og sent på dagen, og tom kalender uten værdata.
- Ingen, én og to pågående hendelser.
- 6 hendelser i morgen, slik at senere dager må utelates; svært travle dager (trinn 3 og 4 i plassregelen).
- En senere dag med for mange hendelser utelates i sin helhet.
- Ingenting under y=452, og alle hendelser i dag og i morgen vises.
- «I morgen» utelates når morgendagen er tom.
- Korte titler og personmerker (inkludert «og», «Alle» og «A»).
- To gjengivelser med samme data gir identiske bilder.

Manuelt:
- Se på bildet fra 2–3 meters avstand. All tekst skal være lesbar.
- Sjekk lange titler, −10° og en dag uten nedbør.

## 10. Prototypen

`kjokkentavle-konsept.html` er oppdatert til v8-oppsettet (lavere hode, «Været i morgen», «A»-merket og utelatt «I morgen»). Den bruker rough.js og Kalam fra `node_modules`. Åpne `#autumn`, `#winter` eller `#quiet` (ingen hendelser i morgen). Plasstrinnene for svært travle dager er bare implementert i `main.py`.
