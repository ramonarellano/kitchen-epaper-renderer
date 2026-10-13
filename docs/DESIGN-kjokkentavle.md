# Kjøkkentavla – designspesifikasjon (v7)

Kjøkkentavla er en håndtegnet familietavle for **Waveshare 7.3" 7-farge e-papir (7.3F)**, 800 × 480 piksler i liggende format.

- Prototype: `kjokkentavle-konsept.html` (én SVG tegnet med rough.js og skriften Kalam).
- Forhåndsvisning av panelet: `panel_kvantisering.py`.
- Referansebilder: `kjokkentavle-v7-host.png` og `kjokkentavle-v7-jul.png`.

## 1. Prinsipper

- **Lesbart fra andre siden av kjøkkenet.** All tekst er minst 22 px. Tidspunkt for siste oppdatering vises ikke.
- **Lite tekst.** Hendelser vises med korte titler. Familiemedlemmer vises som fargede merker, ikke som navn.
- **Alle hendelser i dag og i morgen vises alltid.** Antall dager etter i morgen (0–3) tilpasses plassen som er igjen. En dag vises enten med alle hendelser eller ikke i det hele tatt.
- Teksten er alltid svart på hvitt. Farger brukes bare på figurer, personmerker og markeringer.
- Tegningene har et fast felt som alltid er ledig.

## 2. Panel og rendering

| Punkt | Krav |
|---|---|
| Oppløsning | 800 × 480, liggende. Tegnes rett vei og roteres 180° først i sendesteget, fordi panelet er montert opp ned. |
| Palett (indeks) | 0 svart `#000000`, 1 hvit `#FFFFFF`, 2 grønn `#00FF00`, 3 blå `#0000FF`, 4 rød `#FF0000`, 5 gul `#FFFF00`, 6 oransje `#FF8000` |
| Farger | Bare de sju rene fargene. Ingen gråtoner, ingen gjennomsiktighet og ingen dithering. |
| Kvantisering | Piksler med lav metning (max−min < 60) blir svart hvis luminansen er under ca. 150, ellers hvit. Andre piksler blir nærmeste palettfarge. Dette hindrer fargede kanter rundt tekst. Se `panel_kvantisering.py`. |
| Streker | Minst 1,5 px. |
| rough.js | Fast seed som nullstilles for hver tegning, slik at bildet blir identisk ved samme data og panelet ikke får gjenskygge. |

## 3. Typografi (Kalam 400/700)

| Element | px | Vekt |
|---|---|---|
| Temperatur nå | 36 | 700 |
| Dato | 32 | 700 |
| Nedtelling («19 dager») | 34 | 700 |
| Temperatur i værfeltene | 30 | 700 |
| Hendelsestittel (i dag, i morgen) | 29 | 400 |
| Seksjonstittel («I morgen») | 28 | 700 |
| Hendelser de neste tre dagene (kommaseparert) | 27 | 400 |
| Klokkeslett, ukedag og pågående hendelser | 26 | 700 (tittelen på pågående hendelser er 400) |
| «Været i dag» | 24 | 700 |
| Etiketter (klokkeslett i værfeltene, vind, nedbør, «til Halloween») | 22 | 400 / 700 |
| Bokstav i personmerke | 21 (18 på de neste dagene) | 700 |

Bare linjene for de neste dagene brytes. All annen tekst kortes med «…» hvis den blir for lang.

## 4. Oppsett

```
┌~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~.~┐
│ Mandag 12. oktober ★                              ☾ 6°    │  hode y 14–74
├────────────────────────────────┬─────────────────────────┤
│ ┌ Maria på sykehuset til 18/10 ┐│ Været i dag              │
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

### 4.1 Ramme og hode
- **Ramme: håndtegnet `~.~.~.~`** langs alle fire kanter, fra (11,11) til (789,469). Hver kant deles i like lange enheter på ca. 34 px. Hver enhet er en liten bølge (to kvadratiske kurver med utslag ±6 px, strek 2,2) fulgt av en fylt prikk (diameter 5,5). Antall enheter rundes slik at mønsteret går opp på hver kant. Se `waveBorder()` i prototypen.
- Datoen står til venstre (32 px, grunnlinje y=47). Hodet er gjort lavere enn i v7, slik at innholdet under starter på y=98. **Hele dagen-ikoner for i dag** står rett etter datoen.
- Til høyre står været nå: ikon og temperatur (36 px), høyrejustert mot x=772.
- Håndtegnet strek på y≈63.

### 4.2 Venstre kolonne: agenda
Radhøyden er 33 px. For linjene de neste dagene er den 32 px.

1. **Pågående flerdagshendelser** står øverst i en håndtegnet ramme (strek 1,8), én linje per hendelse. Formatet er personmerker + tittel (26) + **«til D/M»** (26, fet), for eksempel «Maria på sykehuset **til 18/10**» eller «(K) i Bergen **til 15/12**».
   - En hendelse regnes som pågående når den har startet før i dag og varer ut i dag eller lenger.
   - Hendelser som starter i dag og varer flere dager, vises også her.
   - Feltet tegnes ikke når det ikke finnes slike hendelser.
2. **Dagens hendelser:** **alle**, uten tittel, fordi det er gitt at de gjelder i dag.
3. **I morgen:** tittel (28, fet) med eventuelle hele dagen-ikoner etter, og deretter **alle** morgendagens hendelser. Tittelen utelates når det ikke er noen hendelser i morgen.
4. Stiplet håndtegnet skillestrek. Den tegnes bare hvis minst én senere dag får plass.
5. **Dagene etter i morgen** (0–3 dager, i rekkefølge): ukedag (26, fet) og deretter alle dagens hendelser kommaseparert, uten klokkeslett, med personmerker. Linjen brytes mellom hendelser og fortsetter innrykket under.

**Plassregel:** I dag og i morgen har førsteprioritet og vises alltid komplett. Deretter legges dagene etter i morgen til én om gangen, så lenge **hele** dagen får plass (siste grunnlinje ≤ y≈452). Den første dagen som ikke får plass, og alle etter den, utelates. En dag vises aldri halvveis. Se løkken over `later` i prototypen.

**Hvis i dag og i morgen alene ikke får plass** (svært travle dager): reduser radhøyden til ca. 30 px, og som siste utvei vis morgendagens hendelser kommaseparert med klokkeslett, i samme format som de senere dagene.

**Hendelsesrad (i dag og i morgen):** `HH:MM` (fet) → personmerker → kort tittel. Bare starttid vises.

**Hele dagen-hendelser** (søppeltømming, merkedager) får ingen egen rad. De vises som ikon: for i dag etter datoen i hodet, for i morgen etter «I morgen». Flerdagshendelser går i feltet for pågående hendelser.

### 4.3 Personmerker
- Håndtegnet sirkel i personens farge, med svart forbokstav inni.
- Diameter 29 (strek 3,2) på i dag og i morgen. På de neste dagene er diameteren 25 (skala 0,85).
- Flere personer står ved siden av hverandre.

| Navn | Merke | Farge |
|---|---|---|
| Kari | K | rød |
| Ramon | R | grønn |
| Solveig | S | blå |
| Emilie | E | oransje |
| Alle (hele familien) | A | svart |

**Fra kalendertekst til merker** (`people()` i prototypen):
- Prefiks som «K:», «S:», «A:» eller «Alle:» blir merker.
- Navnene ovenfor fjernes fra tittelen og blir merker. Et foranstående «med», «hos» eller «og» fjernes samtidig. Eksempler:
  - «Fotballtrening Emilie» → (E) Fotballtrening
  - «K: Øvelseskjøring med Solveig» → (K)(S) Øvelseskjøring
  - «Luciatog Solveig og Emilie» → (S)(E) Luciatog
- Andre navn (f.eks. Maria, Mariana) blir stående i teksten.

### 4.4 Høyre kolonne: været i dag
- Tittelen «Været i dag» (24, fet) står øverst i kolonnen. Prognosen gjelder **inneværende dag**. Fra kl. 16 vises i stedet «Været i morgen» for neste dag, fordi met.no ikke har data for timer som har passert.
- **Fire like brede felt** (ca. 63 px): kl. **08, 12, 16 og 20**. Hvert felt har:
  - klokkeslett (22, fet) på y=138
  - ikon (sky/regn/snø i skala 1,15, sol i skala 0,85 slik at strålene ikke går inn i nabofeltet)
  - temperatur (30, fet) på y=208
  - vind: lite vind-ikon + m/s som tall (22) på y=238
  - nedbør: blå dråpe + mm (22, fet, blå) på y=264, bare når det er nedbør. Avrundes til hele mm, og under 1 mm vises som «<1».
- Stiplet skillestrek på y≈276.

### 4.5 Sesongfelt (x 530–776, y 290–462)
- **Nedtelling:** ikon + «NN dager» (34, fet) og under det «til <høytid>» (22).
- **Scene:** sesongfigurer på en håndtegnet bakkelinje på y≈452, med noen få dekorfigurer i luften. Figurene må ikke overlappe teksten.

## 5. Korte titler

Kalendertitler gjøres korte, helst ett til to ord.

Foreslått rekkefølge:
1. Bruk et eget felt for kort tittel hvis kalenderen har det, eller en ordliste/overstyring (`"Levere i barnehagen" → "Barnehagen"`).
2. Gjør om familienavn og personprefiks til merker (se 4.3).
3. Kutt etter « – » og « - ».
4. Kutt ved ordgrense til det passer. Bruk «…» bare som siste utvei. Dette gjelder ikke de neste dagene, som brytes over flere linjer i stedet.

## 6. Ikoner og figurer

Alle ikoner og figurer tegnes med rough.js: svart kontur og helfylt i en ren palettfarge.
- **Vær:** sky, regn, snø, måne, sol.
- **Hele dagen:** søppelbøtte, stjerne, fly, tann.
- **Høst:** blader, fluesopp, gresskar, eple, gress.
- **Jul:** grantre, gaver, snøfnugg, stjerne.

## 7. Sesongtema

```js
const THEME = {
  match(date) { /* true når temaet gjelder */ },
  countdown: { label: 'til Halloween', date: '10-31', icon: 'pumpkin' },
  vignette(x, y, w) { /* tegner scenen i sesongfeltet */ }
};
```

Forslag til temaer: høst, Halloween, advent/jul, vinter, påske, 17. mai, sommer. Nedtellingen viser nærmeste kommende høytid.

## 8. Datamodell (eksempel)

Titlene kan komme rett fra kalenderen. Navn og prefiks gjøres om til merker i rendereren.

```js
{
  date: 'Mandag 12. oktober',
  now: { icon: 'moon', temp: '6°' },
  ongoing: [ { title: 'Maria på sykehuset', until: '18/10' } ],
  todayIcons: [],                      // hele dagen-ikoner, vises etter datoen
  today: [ { t: '08:30', title: 'Barnehagen' }, { t: '17:00', title: 'Fotballtrening Emilie' } ],
  tomIcons: ['bin'],
  tomEv: [ { t: '18:30', who: 'K', title: 'Øvelseskjøring med Solveig' }, /* … */ ],
  later: [
    { dn: 'ons', ev: [ { title: 'Tannlege' } ] },
    { dn: 'tor', ev: [ { title: 'Mariana' }, { who: 'KRE', title: 'Høsttreff' },
                       { title: 'Middag hos Solveig' }, { title: 'Yoga Kari' } ] },
    { dn: 'fre', ev: [ { title: 'Lunsj' } ] }
  ],
  wx: [ { k: '08', i: 'cloud', t: '4°', w: 2 }, { k: '12', i: 'sun', t: '8°', w: 3 },
        { k: '16', i: 'sun', t: '9°', w: 3 }, { k: '20', i: 'cloud', t: '6°', w: 2 } ]
}
```

## 9. Testsjekkliste
- Se på panelsimuleringen fra 2–3 meters avstand. All tekst skal være lesbar.
- Test med:
  - ingen, én og to pågående hendelser
  - 5–6 hendelser i morgen, slik at senere dager må utelates
  - mange hendelser på én senere dag, slik at linjen må brytes eller dagen utelates i sin helhet
  - lange titler
  - to–tre personmerker på én hendelse
  - −10° og en dag uten nedbør
- Kontroller at ingenting går forbi y≈462 nederst, at alle hendelser i dag og i morgen vises, og at ingen senere dag vises halvveis.
- To gjengivelser med samme data skal gi piksel-identiske bilder.
- Rotasjonen på 180° skjer bare i sendesteget.
