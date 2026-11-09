"""German umlauts in TruMenu's on-screen texts (owner wish 2026-11-08: "Umlaute im TruMenu sind auch noch nicht ueberall
drin"). TruMenu.cpp is plain ASCII and is compiled without /utf-8, so its German texts were written with ae / oe / ue /
ss. This tool replaces only words from a fixed list (German words whose ae / oe / ue / ss stands for an umlaut or
sharp s) and only inside C string literals - never in code or comments, never in words like "neue", "zuerst",
"Quelle", "request". The umlaut is written as an octal escape of its UTF-8 bytes (\\303\\244 = a-umlaut): octal escapes
stop after three digits, so the letters after them stay letters (a hex escape would swallow "c", "e", "f" ...).
ImGui's default font covers Latin-1, so the menu shows them.

Usage (from the repository root):
  ../bin/pyt -t 120 tools/trumenu_umlauts.py candidates   words with ae / oe / ue / ss inside string literals, with counts,
                                                          marked + (in the list) or ? (not in the list)
  ../bin/pyt -t 120 tools/trumenu_umlauts.py check        how many replacements --write would make (exit 0)
  ../bin/pyt -t 120 tools/trumenu_umlauts.py write        rewrite src/asi/TruMenu/TruMenu.cpp in place (keeps LF / CRLF)
"""
import os
import re
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
OCT = {'ä': r'\303\244', 'ö': r'\303\266', 'ü': r'\303\274', 'Ä': r'\303\204', 'Ö': r'\303\226', 'Ü': r'\303\234',
       'ß': r'\303\237'}
# ASCII spelling -> German spelling (only words that really carry an umlaut / sharp s)
WORDS = {}


def add(*pairs):
    for p in pairs:
        a, b = p.split('=')
        WORDS[a] = b


add('fuer=für', 'ueber=über', 'Ueber=Über', 'zurueck=zurück', 'Zurueck=Zurück', 'waehlen=wählen', 'Waehlen=Wählen',
    'gewaehlt=gewählt', 'Flaeche=Fläche', 'Flaechen=Flächen', 'Laufflaeche=Lauffläche', 'Laufflaechen=Laufflächen',
    'Rutschflaechen=Rutschflächen', 'Oberflaeche=Oberfläche', 'Nachbarflaeche=Nachbarfläche', 'Gelaende=Gelände',
    'zusaetzlich=zusätzlich', 'spaeter=später', 'pruefen=prüfen', 'Pruefen=Prüfen', 'geprueft=geprüft',
    'naechste=nächste', 'Naechste=Nächste', 'Naechstes=Nächstes', 'Naechster=Nächster', 'naechsten=nächsten',
    'laenger=länger', 'klaeren=klären', 'haelt=hält', 'anhaelt=anhält', 'groesser=größer', 'Groesse=Größe',
    'groesste=größte', 'gefuellt=gefüllt', 'fuellen=füllen', 'Fuellen=Füllen', 'gefaerbt=gefärbt', 'faerbt=färbt',
    'daempfen=dämpfen', 'Zaehlt=Zählt', 'zaehlt=zählt', 'Zaehler=Zähler', 'zaehler=zähler', 'Waenden=Wänden',
    'Spielstaende=Spielstände', 'Spielstaenden=Spielständen', 'Raetsel=Rätsel', 'Paesse=Pässe', 'Kostueme=Kostüme',
    'Kostuem=Kostüm', 'Geraeusch=Geräusch', 'Geraeusche=Geräusche', 'Hoeren=Hören', 'hoeren=hören', 'Schluessel=Schlüssel',
    'moeglich=möglich', 'Moeglich=Möglich', 'loeschen=löschen', 'Loeschen=Löschen', 'geloescht=gelöscht',
    'Ausloeser=Auslöser', 'Tueren=Türen', 'Tuer=Tür', 'aendern=ändern', 'Aendern=Ändern', 'geaendert=geändert',
    'Aenderung=Änderung', 'Aenderungen=Änderungen', 'oeffnen=öffnen', 'Oeffnen=Öffnen', 'geoeffnet=geöffnet',
    'schliessen=schließen', 'Schliessen=Schließen', 'gross=groß', 'Gross=Groß', 'grosse=große', 'grossen=großen',
    'Fuesse=Füße', 'Fuss=Fuß', 'Hoehe=Höhe', 'hoeher=höher', 'Kaempfe=Kämpfe', 'Kaempfer=Kämpfer', 'Kaempfen=Kämpfen',
    'Waffe=Waffe', 'Gegenstaende=Gegenstände', 'Gegenstaenden=Gegenständen', 'Staerke=Stärke', 'staerker=stärker',
    'Schaetze=Schätze', 'Schaedel=Schädel', 'Faehigkeit=Fähigkeit', 'Faehigkeiten=Fähigkeiten', 'Muenzen=Münzen',
    'Gruen=Grün', 'gruen=grün', 'Ruestung=Rüstung', 'Bruecke=Brücke', 'Huegel=Hügel', 'Huelle=Hülle', 'Ueberblick=Überblick',
    'Uebersicht=Übersicht', 'uebersprungen=übersprungen', 'ueberspringen=überspringen', 'Ueberspringen=Überspringen',
    'Rueckweg=Rückweg', 'Rueckkehr=Rückkehr', 'Rueckgaengig=Rückgängig', 'Schaltflaeche=Schaltfläche',
    'Spieloeffnung=Spielöffnung', 'Kaefig=Käfig', 'Laerm=Lärm', 'laeuft=läuft', 'Laeuft=Läuft', 'faellt=fällt',
    'Faellt=Fällt', 'Zufaellig=Zufällig', 'zufaellig=zufällig', 'Waehrend=Während', 'waehrend=während', 'Maenner=Männer',
    'koennen=können', 'Koennen=Können', 'kuerzer=kürzer', 'Kuerzel=Kürzel', 'muessen=müssen', 'Muessen=Müssen',
    'wuerde=würde', 'duerfen=dürfen', 'Pruefung=Prüfung', 'Pruefungen=Prüfungen', 'Erklaerung=Erklärung',
    'erklaert=erklärt', 'Naehe=Nähe', 'naeher=näher', 'Lebensenergie=Lebensenergie', 'Hoehle=Höhle', 'Hoehlen=Höhlen',
    'Gefaess=Gefäß', 'Gefaesse=Gefäße', 'Kruege=Krüge', 'Topfe=Topfe', 'Toepfe=Töpfe', 'Saeule=Säule', 'Saeulen=Säulen',
    'Haende=Hände', 'Haenden=Händen', 'Fluegel=Flügel', 'Ausgaenge=Ausgänge', 'Eingaenge=Eingänge', 'Uebergang=Übergang',
    'Uebergaenge=Übergänge', 'Fuehrung=Führung', 'ausfuehren=ausführen', 'Ausfuehren=Ausführen', 'ausgefuehrt=ausgeführt',
    'Begruendung=Begründung', 'Gruende=Gründe', 'gueltig=gültig', 'ungueltig=ungültig', 'Ungueltig=Ungültig',
    'Abkuerzung=Abkürzung', 'Stuetze=Stütze', 'Stuecke=Stücke', 'Stueck=Stück', 'Luecke=Lücke', 'Luecken=Lücken',
    'Schatztruhe=Schatztruhe', 'Ruecken=Rücken', 'ruecken=rücken', 'Bodenhoehe=Bodenhöhe', 'Sprunghoehe=Sprunghöhe',
    'Faehrte=Fährte', 'Gaeste=Gäste', 'Schluesselwort=Schlüsselwort', 'Hinweisfenster=Hinweisfenster',
    'Fehlerkaesten=Fehlerkästen', 'Kaesten=Kästen', 'Kasten=Kasten', 'Taster=Taster', 'Tastenkuerzel=Tastenkürzel',
    'Schwaeche=Schwäche', 'Naechtliche=Nächtliche', 'Groessen=Größen', 'Kaelte=Kälte', 'Waerme=Wärme', 'Laenge=Länge',
    'Waende=Wände', 'Waenden=Wänden', 'Gefaelle=Gefälle', 'Raeume=Räume', 'Raeumen=Räumen', 'raeumen=räumen',
    'Abstaende=Abstände', 'Zustaende=Zustände', 'Zustaenden=Zuständen', 'Bloecke=Blöcke', 'Kuegelchen=Kügelchen',
    'Kugeln=Kugeln', 'Stroemung=Strömung', 'Stroeme=Ströme', 'Kraefte=Kräfte', 'Faehrt=Fährt', 'faehrt=fährt',
    'Aufzuege=Aufzüge', 'Aufzug=Aufzug', 'Schalter=Schalter', 'Gebaeude=Gebäude', 'Haenger=Hänger', 'Haengen=Hängen',
    'haengt=hängt', 'Haengt=Hängt', 'Uebung=Übung', 'Uebungen=Übungen', 'Ueberschrift=Überschrift', 'Taeuschung=Täuschung',
    'Gefuehl=Gefühl', 'Kuehl=Kühl', 'kuehl=kühl', 'Kuehle=Kühle', 'Verzoegerung=Verzögerung', 'verzoegert=verzögert',
    'Toene=Töne', 'Toenen=Tönen', 'Schoen=Schön', 'schoen=schön', 'Gewaesser=Gewässer', 'Fluessigkeit=Flüssigkeit',
    'Haeufig=Häufig', 'haeufig=häufig', 'Haeufigkeit=Häufigkeit', 'Hilfsmaessig=Hilfsmäßig', 'regelmaessig=regelmäßig',
    'Maessig=Mäßig', 'maessig=mäßig', 'Massstab=Maßstab', 'Strasse=Straße', 'heisst=heißt', 'weiss=weiß', 'Weiss=Weiß',
    'Spass=Spaß', 'aussen=außen', 'Aussen=Außen', 'ausserhalb=außerhalb', 'Ausserhalb=Außerhalb', 'gemaess=gemäß',
    'Fuellstand=Füllstand', 'Ueberlauf=Überlauf', 'Laufbaender=Laufbänder', 'Baender=Bänder', 'Maengel=Mängel',
    'ausgewaehlt=ausgewählt', 'Ausgewaehlt=Ausgewählt', 'Auswaehlen=Auswählen', 'auswaehlen=auswählen',
    # from `candidates` on 2026-11-09 (German words in TruMenu's strings)
    'laedt=lädt', 'Koerper=Körper', 'enthaelt=enthält', 'Doppelgaengerin=Doppelgängerin', 'Toeten=Töten',
    'toeten=töten', 'toetet=tötet', 'Fuers=Fürs', 'fuers=fürs', 'Sammelgegenstaende=Sammelgegenstände',
    'Zaehlung=Zählung', 'aendert=ändert', 'Ausruestung=Ausrüstung', 'Lautstaerke=Lautstärke', 'Menue=Menü',
    'einfaerben=einfärben', 'fuehrt=führt', 'hoerbare=hörbare', 'loescht=löscht', 'zurueckspielen=zurückspielen',
    'Auffuellen=Auffüllen', 'Betaeubungsgewehr=Betäubungsgewehr', 'Bildgroesse=Bildgröße', 'Eintraege=Einträge',
    'naechster=nächster', 'Fuellung=Füllung', 'Grosskatze=Großkatze', 'Plaetze=Plätze', 'Soeldner=Söldner',
    'Umhuellende=Umhüllende', 'umhuellende=umhüllende', 'ergaenzen=ergänzen', 'gekuerzt=gekürzt', 'laesst=lässt',
    'loesen=lösen', 'uebernehmen=übernehmen', 'ueberschreibt=überschreibt', 'verfuegbar=verfügbar',
    'zuruecksetzen=zurücksetzen')
WORDS = {a: b for a, b in WORDS.items() if a != b}

STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')
WORD = re.compile(r'[A-Za-zÄÖÜäöüß]+')


def literal_spans(text):
    """(start, end) of every C string literal outside comments"""
    spans, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif c == "'":                           # char literal like '"' or '\''
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == '\\' else 1
            i = j + 1
        elif c == '"':
            m = STRING.match(text, i)
            if not m:
                i += 1
                continue
            spans.append((m.start(), m.end()))
            i = m.end()
        else:
            i += 1
    return spans


def convert_word(w):
    g = WORDS.get(w)
    if g is None:
        return None
    return ''.join(OCT.get(ch, ch) for ch in g)


def main(argv):
    if not argv or argv[0] not in ('candidates', 'check', 'write'):
        sys.exit(__doc__)
    raw = open(SRC, 'rb').read()
    text = raw.decode('latin-1')
    # the option table kOpts (key comments written into TruMenu.ini, which Windows reads as ANSI and
    # tools/trumenu_ini_check.py compares with the sample INI) stays ASCII
    a0 = text.find('const OptDef kOpts[] = {')
    b0 = text.find('const char *const kIniHeader', a0)
    spans = [s for s in literal_spans(text) if a0 < 0 or b0 < 0 or not (a0 <= s[0] < b0)]
    if argv[0] == 'candidates':
        seen = {}
        for a, b in spans:
            for m in WORD.finditer(text, a, b):
                w = m.group(0)
                if re.search(r'ae|oe|ue|Ae|Oe|Ue|ss', w):
                    seen[w] = seen.get(w, 0) + 1
        for w, c in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0])):
            print('%s %-28s %d' % ('+' if w in WORDS else '?', w, c))
        return 0
    out, last, count, words = [], 0, 0, {}
    for a, b in spans:
        out.append(text[last:a])
        lit = text[a:b]

        def rep(m):
            nonlocal count
            c = convert_word(m.group(0))
            if c is None:
                return m.group(0)
            count += 1
            words[m.group(0)] = words.get(m.group(0), 0) + 1
            return c
        # never inside an existing escape sequence: words are letters only, escapes start with a backslash
        out.append(re.sub(r'(?<![\\A-Za-z])[A-Za-z]+', rep, lit))
        last = b
    out.append(text[last:])
    new = ''.join(out)
    print('%d replacements in %d words: %s' % (count, len(words),
          ', '.join('%s %d' % kv for kv in sorted(words.items(), key=lambda kv: -kv[1]))))
    if argv[0] == 'write' and count:
        open(SRC, 'wb').write(new.encode('latin-1'))
        print('written: ' + os.path.normpath(SRC))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
