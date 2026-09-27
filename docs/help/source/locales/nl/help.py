"""Dutch content for the full Help manual.

Mirrors locales/en/help.py chapter for chapter and block for block; the
content loader refuses to build if the structure drifts. Code blocks (file
names, commands, PC-report section names) stay in English on purpose: they
are what the reader sees on screen.
"""
from __future__ import annotations

CHAPTERS: list[dict] = [
    {
        "id": "introduction",
        "title": "Inleiding",
        "blocks": [
            {"type": "para", "text": (
                "NVC is een Windows-videoconverter gebouwd rond FFmpeg. Het bewaakt een "
                "bronmap, converteert ondersteunde media, inspecteert media-informatie, neemt "
                "tot vier bronnen op, speelt media naast elkaar af, genereert een PC-rapport en "
                "kan originele bestanden na conversie opruimen.")},
            {"type": "figure", "fig_id": "FIG-00"},
            {"type": "note", "items": [
                "Overschrijfbeleid: NVC overschrijft nooit een al geconverteerde video. Als de "
                "doelmap al video.mp4 bevat, wordt de volgende uitvoer video (1).mp4, daarna "
                "video (2).mp4 -- dezelfde stijl die webbrowsers gebruiken voor dubbele "
                "downloads.",
            ]},
        ],
    },
    {
        "id": "quick-start",
        "title": "Snel aan de slag",
        "blocks": [
            {"type": "para", "text": "Zes stappen van een verse installatie naar een geconverteerd bestand."},
            {"type": "steps", "items": [
                "Open Instellingen via het menu.",
                "Kies op het tabblad Mappen de Bronmap.",
                "Kies op het tabblad Mappen de Doelmap.",
                "Kies op het tabblad Formaat het Uitvoerformaat, de Videocodec en de "
                "Audiocodec. De standaardwaarden passen bij de meeste situaties.",
                "Klik op OK en daarna op Start.",
                "Zet video's in de bronmap.",
            ]},
            {"type": "figure", "fig_id": "FIG-01"},
        ],
    },
    {
        "id": "main-window",
        "title": "Overzicht van het hoofdvenster",
        "blocks": [
            {"type": "para", "text": (
                "Het hoofdvenster is ingedeeld in tabbladen, met een zijbalk links en een "
                "statusvoettekst. Onder het logo benoemt de zijbalk het huidige tabblad: een "
                "pictogram voor het hulpmiddel (een vergrootglas met een oog voor de Mediaspeler, "
                "een pijlencirkel rond een afspeelsymbool voor de Videoconverter, een camera voor "
                "de Recorder, een schaar voor de Verliesvrije editor, een monitor voor PC-rapport), "
                "de titel van het tabblad en een beschrijving van één regel, daarna het "
                "voorbeeldvak en de knop Start. Sleep een tabblad langs de tabbladbalk om de "
                "tabbladen in de gewenste volgorde te zetten; klik met de rechtermuisknop op een "
                "tabblad om dat hulpmiddel te verbergen en haal het terug via Menu -- "
                "Hulpmiddelen. NVC onthoudt beide.")},
            {"type": "table", "headers": ("Onderdeel", "Wat het doet"), "rows": [
                ("Videoconverter",
                 "De tabel Geconverteerde bestanden (conversies in de wachtrij, in "
                 "verwerking, geslaagd en mislukt) boven het conversielogboek met zijn "
                 "meldingen, voortgang, waarschuwingen en resultaten. Sleep de scheidingsbalk "
                 "ertussen. De tabel Huidige video-instellingen naast het logboek vat formaat, "
                 "codecs, resolutie, bitrate en framesnelheid samen; klik erop om de "
                 "Formaat-instellingen te openen."),
                ("PC-rapport",
                 "Genereert een PC-rapport voor ondersteuning en probleemoplossing."),
                ("Verliesvrije editor",
                 "Biedt hulpmiddelen voor knippen, remuxen, samenvoegen en het kopiëren van "
                 "audiostreams."),
                ("Multibron-recorder",
                 "Neemt tot vier videobronnen op."),
                ("Mediaspeler",
                 "Speelt media af in één, twee of vier panelen, met een Inspecteren-paneel dat "
                 "de ffprobe-samenvatting en JSON van de geselecteerde clip toont."),
                ("Voorbeeldpaneel",
                 "Het bladvormige vak in de zijbalk toont een voorbeeld van het huidige bestand "
                 "of de recorderindeling, en een kloppend hart terwijl een PC-rapport wordt "
                 "gemaakt. Het is leeg als er niets te tonen is."),
                ("Menu",
                 "Opent Info, Help, mappen, Instellingen, Venster, Hulpmiddelen, Taal, updates "
                 "en Afsluiten."),
            ]},
            {"type": "note", "items": [
                "PC-rapport en Verliesvrije editor zijn standaard verborgen. Schakel ze in via "
                "Menu -- Hulpmiddelen of Instellingen -- Hulpmiddelen. Afspelen of Inspecteren in "
                "Mediaspeler toont het tabblad Mediaspeler voor de huidige sessie, ook als het is "
                "uitgeschakeld. Het laatste zichtbare hulpmiddel kan niet worden verborgen.",
                "Het Menu bevat Info, Help, Bronmap openen, Doelmap openen, Back-upmap openen, "
                "Instellingen, Venster, Hulpmiddelen, Taal, Controleren op updates en Afsluiten.",
                "De voettekst heeft de knop Start/Stop, een slotpictogram, een bestandskiezer, "
                "een bezem en een statuslabel. Op het recordertabblad heet de knop Opname "
                "starten of Opname stoppen. Het slotpictogram vergrendelt de instellingen en de "
                "Start-knop heet dan Vergrendeld. De bestandskiezer selecteert mediabestanden "
                "om te converteren en de bezem maakt het logboek leeg.",
                "Het statuslabel is op elk tabblad hetzelfde en vermeldt alles wat loopt -- "
                "Opname, Converteren, Bewaken of Vergrendeld -- gescheiden door punten; als er "
                "niets loopt staat er Inactief. De stip is groen terwijl een taak loopt, "
                "oranje als alleen de mapbewaking aan staat, rood na een mislukte opname en "
                "grijs als NVC vergrendeld is.",
                "Wisselen van tabblad stopt nooit iets: opnemen, converteren, mapbewaking en "
                "media-afspelen gaan door welk tabblad ook vooraan staat, en geen tabblad wordt "
                "ooit grijs. Opnemen is exclusief ten opzichte van de andere ffmpeg-taken: "
                "terwijl een opname start, loopt of stopt, heet de Start-knop op het "
                "convertertabblad Opname bezig... en zijn Knippen, Remuxen, Audio uitpakken, "
                "Audio verwijderen en Samenvoegen van de Verliesvrije editor grijs, elk met de "
                "reden als knopinfo. Terwijl een conversie of de mapbewaking loopt, is Opname "
                "starten niet beschikbaar (de knop heet Converteren...), maar de rest van de "
                "recorder -- voorbeelden, instellingen, apparaten -- blijft bruikbaar. "
                "Mediaspeler en PC-rapport werken altijd.",
                "Klikken op X sluit NVC standaard af. Vink \"Sluiten bij X (niet minimaliseren "
                "naar systeemvak)\" uit in Instellingen -- Algemeen om in plaats daarvan naar "
                "het systeemvak te minimaliseren. Het systeemvakmenu heeft Tonen en Afsluiten. "
                "Er kan maar één exemplaar van NVC tegelijk draaien.",
            ]},
        ],
    },
    {
        "id": "converting-files",
        "title": "Bestanden converteren",
        "blocks": [
            {"type": "para", "text": (
                "Als het bewaken actief is, let NVC in de bronmap op nieuwe ondersteunde "
                "video's. Het scant ook de bestaande bestanden in die map wanneer het bewaken "
                "start.")},
            {"type": "para", "text": (
                "U kunt bestanden naar beide helften van het tabblad Videoconverter slepen. U "
                "kunt ook de bestandskiezer in de voettekst gebruiken om mediabestanden te "
                "selecteren om te converteren.")},
            {"type": "para", "text": (
                "NVC beschermt bestaande geconverteerde bestanden. Als een uitvoernaam al "
                "bestaat, kiest NVC de eerstvolgende vrije bestandsnaam in browserstijl:")},
            {"type": "code", "lines": [
                "Session.mp4",
                "Session (1).mp4",
                "Session (2).mp4",
            ]},
            {"type": "para", "text": (
                "NVC accepteert gangbare videoformaten, waaronder MP4, AVI, WMV, MKV, FLV, WebM, "
                "MOV, MPEG, MPG, M4V, 3GP, TS, VOB, RM, RMVB, ASF, M2TS, MTS, OGV, DIVX, DV en "
                "F4V.")},
            {"type": "figure", "fig_id": "FIG-03"},
        ],
    },
    {
        "id": "conversion-settings",
        "title": "Conversie-instellingen",
        "blocks": [
            {"type": "para", "text": (
                "Instellingen heeft zes tabbladen: Algemeen, Mappen, Verwijderen, Formaat, Tijd "
                "en Hulpmiddelen. Standaard herstelt elke waarde, OK slaat op en Annuleren "
                "verwerpt de wijzigingen.")},
            {"type": "figure", "fig_id": "FIG-02"},
            {"type": "para", "text": "Het tabblad Algemeen regelt het gedrag van de toepassing en GPU-codering."},
            {"type": "table", "headers": ("Instelling", "Toelichting"), "rows": [
                ("Automatisch starten bij opstarten",
                 "Start het bewaken automatisch met de vorige instellingen."),
                ("Alleen kopiëren",
                 "Remuxt de bronstreams naar het gekozen Uitvoerformaat zonder opnieuw te "
                 "coderen (FFmpeg -c copy), wat snel is maar mislukt als de container de "
                 "bronstreams niet kan bevatten. Remuxen in de Verliesvrije editor doet "
                 "hetzelfde voor losse bestanden."),
                ("Sluiten bij X (niet minimaliseren naar systeemvak)",
                 "Standaard aangevinkt. Vink het uit om NVC naar het systeemvak te "
                 "minimaliseren als u op X klikt."),
                ("Starten bij het opstarten van Windows (alle gebruikers)",
                 "Start NVC wanneer Windows start voor alle gebruikers; vereist rechten."),
                ("GPU-versnelling gebruiken",
                 "Schakelt GPU-versnelling in wanneer die wordt ondersteund."),
                ("GPU-encoder",
                 "Kies Auto, nvidia, intel of amd."),
            ]},
            {"type": "para", "text": "Het tabblad Mappen kiest de mappen die NVC gebruikt."},
            {"type": "table", "headers": ("Instelling", "Toelichting"), "rows": [
                ("Bronmap", "Klik op Wijzigen om de map te kiezen die NVC bewaakt en scant."),
                ("Doelmap", "Klik op Wijzigen om te kiezen waar geconverteerde bestanden worden geschreven."),
                ("Back-upmap", "Klik op Wijzigen om te kiezen waarheen geback-upte originelen worden verplaatst."),
                ("Logboekmap",
                 r"Waar de conversielogboeken per bestand worden geschreven. Laat het leeg "
                 r"voor de standaardmap, %APPDATA%\NVC\logs. Het hoofdlogboek van de "
                 r"toepassing blijft altijd in de standaardmap, omdat het wordt geopend "
                 r"voordat de instellingen zijn gelezen."),
            ]},
            {"type": "para", "text": (
                "Het tabblad Verwijderen regelt de originele bestanden. Zie het hoofdstuk "
                "Omgang met originele bestanden.")},
            {"type": "para", "text": "Het tabblad Formaat regelt de conversie-uitvoer."},
            {"type": "table", "headers": ("Instelling", "Toelichting"), "rows": [
                ("Uitvoerformaat",
                 "Kies mp4, mov, avi, mkv, flv, webm, mpeg, mpg, 3gp, ogg, wmv, m4v, mp3 "
                 "of gif."),
                ("Videocodec",
                 "Kies libx264, mpeg4, libvpx, hevc, flv, libtheora of wmv2."),
                ("Audiocodec",
                 "Kies aac, mp3, ac3, opus of vorbis."),
                ("GIF-opties",
                 "FPS, Maximale breedte, Herhalen en Snelle GIF (zonder palet) verschijnen als "
                 "het Uitvoerformaat gif is."),
                ("Geavanceerde opties tonen",
                 "Toont Videoformaat, Bitrate, Framesnelheid, Keyframe-interval (GOP), Volume, "
                 "Tekstoverlay en Console-integratie."),
                ("Videoformaat",
                 "Kies Auto, 640x480, 1280x720, 1920x1080 of 3840x2160."),
                ("Bitrate",
                 "Kies Auto of een waarde uit de lijst van 512k tot 3000k."),
                ("Framesnelheid",
                 "Kies Auto of een snelheid uit de lijst van 8 tot 60."),
                ("Keyframe-interval (GOP)",
                 "Kies 0 voor Auto of een waarde tot 300."),
                ("Volume",
                 "Stel het uitvoervolume van de audio in van 0 tot 500 %."),
                ("Tekstoverlay",
                 "Voegt tekst toe aan de uitvoer. Zie het hoofdstuk Tekstoverlays."),
                ("Console-integratie",
                 "Voegt aangepaste FFmpeg-vlaggen toe aan de opdracht."),
                ("Voorinstellingen",
                 "Gebruik Ethovision, Aangepast 1, Aangepast 2, Opslaan in 1 of Opslaan in 2."),
            ]},
            {"type": "para", "text": "Het tabblad Tijd beperkt wanneer een conversie mag starten."},
            {"type": "table", "headers": ("Instelling", "Toelichting"), "rows": [
                ("Geen tijdsbeperkingen", "Staat conversie op elk moment toe."),
                ("Starttijd", "Stelt het begin van het toegestane conversievenster in."),
                ("Eindtijd", "Stelt het einde van het toegestane conversievenster in. Zie Tijdsbeperkingen."),
            ]},
            {"type": "para", "text": "Het tabblad Hulpmiddelen regelt welke tabbladen in het hoofdvenster verschijnen."},
            {"type": "table", "headers": ("Instelling", "Toelichting"), "rows": [
                ("Selectievakjes voor hulpmiddelen",
                 "Er is één selectievakje per tabblad. Niet-aangevinkte tabbladen worden in het "
                 "hoofdvenster verborgen. Dezelfde lijst staat in Menu -- Hulpmiddelen, en met "
                 "de rechtermuisknop op een tabblad verbergt u het; het laatste zichtbare "
                 "hulpmiddel blijft altijd staan."),
            ]},
        ],
    },
    {
        "id": "gpu-encoding",
        "title": "GPU-codering",
        "blocks": [
            {"type": "para", "text": (
                "Indien ingeschakeld probeert NVC een ondersteunde GPU-encoder van NVIDIA, AMD "
                "of Intel te gebruiken. GPU-codering kan veel sneller zijn dan CPU-codering, "
                "maar de beschikbare codecs hangen af van de geïnstalleerde "
                "GPU-stuurprogramma's en de FFmpeg-build.")},
            {"type": "code", "lines": [
                "H.264 GPU encoders:  h264_nvenc   h264_amf   h264_qsv",
                "HEVC  GPU encoders:  hevc_nvenc   hevc_amf   hevc_qsv",
            ]},
            {"type": "note", "items": [
                "Als de gekozen GPU-encoder niet beschikbaar is, valt NVC waar mogelijk terug "
                "op CPU-codering.",
                "De detectie draait één keer per sessie en wordt in de cache bewaard. Als u "
                "nieuwe GPU-stuurprogramma's installeert, start NVC dan opnieuw zodat het de "
                "beschikbare encoders opnieuw detecteert.",
            ]},
        ],
    },
    {
        "id": "gif-export",
        "title": "GIF-export",
        "blocks": [
            {"type": "para", "text": (
                "GIF-uitvoer kan een paletworkflow in twee stappen gebruiken voor betere "
                "kleurkwaliteit. U kunt FPS, Maximale breedte en Herhalen aanpassen, of Snelle "
                "GIF (zonder palet) kiezen. Een lagere FPS en een kleinere Maximale breedte "
                "verkleinen beide het bestand.")},
            {"type": "note", "items": [
                "GIF-bestanden worden snel groot. Converteer lange clips liever naar MP4.",
            ]},
        ],
    },
    {
        "id": "text-overlays",
        "title": "Tekstoverlays",
        "blocks": [
            {"type": "para", "text": (
                "Tekstoverlay brandt de gekozen tekst in de uitvoervideo.")},
            {"type": "table", "headers": ("Overlay", "Toont"), "rows": [
                ("Geen", "Geen overlay."),
                ("Verstreken tijd", "De verstreken afspeeltijd."),
                ("Opnametijd", "Het tijdstip van de opname."),
                ("Opnamedatum/-tijd", "De datum en tijd van de opname."),
                ("Opnamedatum/-tijd + resterend",
                 "De datum en tijd van de opname op één regel en de resterende seconden op een "
                 "andere."),
                ("CRTV Cam", "Een knipperend REC-label en de opnametijd."),
            ]},
            {"type": "note", "items": [
                "Overlays vereisen videofiltering en kunnen de GPU-compatibiliteit en de "
                "conversiesnelheid verminderen.",
                "Opname-overlays gebruiken de opnametijd van het bestand als die aanwezig is "
                "en anders de wijzigingstijd van het bestand.",
            ]},
        ],
    },
    {
        "id": "original-files",
        "title": "Omgang met originele bestanden",
        "blocks": [
            {"type": "table", "headers": ("Optie", "Gedrag"), "rows": [
                ("Bestanden verwijderen na conversie",
                 "Verwijdert het origineel na een geslaagde conversie, direct als de "
                 "bewaartermijn 0 is of anders na de bewaartermijn."),
                ("Bewaartermijn (dagen)",
                 "Kies 0 tot 30 dagen. Wachtende verwijderingen worden op schijf opgeslagen en "
                 "na een herstart verwerkt."),
                ("Back-upmap gebruiken",
                 "Verplaatst originelen naar de Back-upmap in plaats van ze te verwijderen."),
            ]},
            {"type": "note", "items": [
                "Bewaar originelen totdat u hebt bevestigd dat de geconverteerde bestanden "
                "goed afspelen.",
            ]},
        ],
    },
    {
        "id": "time-restrictions",
        "title": "Tijdsbeperkingen",
        "blocks": [
            {"type": "para", "text": (
                "Instellingen -- Tijd laat u Geen tijdsbeperkingen kiezen of een Starttijd en "
                "Eindtijd voor conversie instellen.")},
            {"type": "note", "items": [
                "Een bestand dat buiten het venster wordt gedetecteerd, wordt overgeslagen met "
                "\"Huidige tijd buiten toegestaan bereik\" in het conversielogboek. Het wordt "
                "niet voor later in de wachtrij gezet. Zet het bestand opnieuw neer, of laat "
                "het bewaken het opnieuw detecteren, binnen het toegestane venster.",
                "Een Eindtijd die vroeger is dan de Starttijd betekent een nachtelijk venster.",
                "De standaardwaarde is Geen tijdsbeperkingen.",
            ]},
        ],
    },
    {
        "id": "converted-files",
        "title": "Videoconverter: Geconverteerde bestanden",
        "blocks": [
            {"type": "para", "text": (
                "Het tabblad Videoconverter toont de tabel Geconverteerde bestanden boven het "
                "conversielogboek; sleep de scheidingsbalk ertussen om de verdeling te "
                "wijzigen. De tabel heeft de kolommen Bestandsnaam, Doelmap en Gewijzigd op. "
                "Statuspictogrammen geven conversies in de wachtrij, in verwerking, geslaagd en "
                "mislukt aan. Afspelen en Inspecteren zijn kleine pictogramknoppen onder de "
                "rechterrand van de tabel; ze verschijnen zodra een rij is geselecteerd. De "
                "overige acties staan in het contextmenu van de rij. Rechtsklikken op het lege "
                "deel van de tabel biedt Video's toevoegen om te converteren... en Een map "
                "bewaken.... Zolang de tabel leeg is, markeren dunne grijze lijnen waar de "
                "rijen komen. De bestandsknop in de voettekst voegt video's toe om te "
                "converteren en de bezem maakt de tabel samen met het logboek leeg.")},
            {"type": "table", "headers": ("Bediening", "Wat het doet"), "rows": [
                ("Afspelen", "Opent het geselecteerde bestand op het tabblad Mediaspeler."),
                ("Inspecteren", "Opent het geselecteerde bestand in de Mediaspeler met het Inspecteren-paneel dat de ffprobe-gegevens toont."),
                ("Video's toevoegen om te converteren...", "Opent de bestandskiezer, hetzelfde als de knop Bestanden toevoegen."),
                ("Een map bewaken...", "Kiest een map om te bewaken; die wordt de Bronmap in Instellingen. Als het bewaken loopt, start het opnieuw op de nieuwe map."),
                ("De map van dit bestand bewaken", "Maakt de map van het geselecteerde bestand de Bronmap."),
                ("Afspelen in Mediaspeler", "Opent het geselecteerde bestand op het tabblad Mediaspeler."),
                ("Inspecteren in Mediaspeler", "Hetzelfde als de knop Inspecteren."),
                ("Openen in", "Submenu: Mediaspeler, Verliesvrije editor (vult het invoerbestand en toont het tabblad) of de standaard-app van Windows."),
                ("Bovenliggende map openen", "Opent de doelmap van het geselecteerde bestand."),
                ("Logbestand openen", "Opent een venster met het conversielogboek van dat bestand."),
                ("Bestandspad kopiëren", "Kopieert het pad van het geselecteerde bestand."),
                ("Instellingen", "Opent Instellingen."),
            ]},
        ],
    },
    {
        "id": "media-inspection",
        "title": "Media-inspectie",
        "blocks": [
            {"type": "para", "text": (
                "Media-inspectie zit in de Mediaspeler: het Inspecteren-paneel naast de video "
                "(standaard open; de vergrootglasknop op de bedieningsbalk verbergt en toont "
                "het) heeft de subtabbladen Samenvatting en Gedetailleerde JSON voor de clip "
                "van het geselecteerde paneel. Een ander paneel selecteren, of een ander "
                "bestand in het geselecteerde paneel laden, werkt het bij. Sleep de "
                "scheidingsbalk tussen de video en het paneel om het te vergroten of te "
                "verkleinen; het paneel behoudt zijn aandeel van het venster als het venster "
                "groeit. Zet een bestand neer op een van beide subtabbladen om dat bestand te "
                "inspecteren zonder het te laden. Samenvatting vermeldt Bestand, Container, "
                "Duur, Grootte, Bitrate en Aantal streams. Daarna volgt elke video-, audio- en "
                "ondertitelstream, inclusief codec en de van toepassing zijnde resolutie, "
                "framesnelheid of kanalen. Een blok Keyframe-analyse (eerste 30 s) volgt op "
                "de streamgegevens. Gedetailleerde JSON toont de ruwe uitvoer van ffprobe "
                "-print_format json.")},
            {"type": "figure", "fig_id": "FIG-04"},
        ],
    },
    {
        "id": "pc-report",
        "title": "Hulpmiddel PC-rapport",
        "blocks": [
            {"type": "para", "text": (
                "Het hulpmiddel PC-rapport verzamelt systeeminformatie voor ondersteuning en "
                "probleemoplossing.")},
            {"type": "steps", "items": [
                "Klik op PC-rapport genereren.",
                "Wacht tot het verzamelen klaar is. Sommige verzamelaars kunnen even duren.",
                "Klik op Rapport openen om de gegenereerde HTML te openen. Map openen opent de "
                "map waarin het rapport is geschreven.",
                "Rapporten worden standaard op uw Bureaublad opgeslagen, met het padpatroon "
                "Desktop\\PC_Report_JJJJMMDD_UUMMSS.html. Als er geen map Bureaublad is, "
                "gebruikt NVC uw gebruikersprofielmap. Als die bestandsnaam al bestaat, kiest "
                "NVC een unieke naam en overschrijft het bestaande bestand nooit.",
            ]},
            {"type": "figure", "fig_id": "FIG-05"},
            {"type": "para", "text": (
                "Het rapport opent met Rapportgezondheid (timing, lege secties en "
                "waarschuwingen) en daarna deze secties:")},
            {"type": "code", "lines": [
                "Noldus Summary",
                "Operating System",
                "Installed Updates",
                "Licenses",
                "System Directories",
                "System Files",
                "Installed Programs",
                "Security",
                "Accessibility",
                "Environment",
                "Regional Settings",
                "Processes",
                "Services",
                "Drivers",
                "Autorun",
                "Codecs",
                "MMC Snap-ins",
                "System Summary",
                "Motherboard",
                "BIOS",
                "CPU",
                "Memory",
                "Sensors",
                "Devices",
                "PCI",
                "System Slots",
                "Network Adapters",
                "Video",
                "Monitors",
                "Sound",
                "Storage Devices",
                "Logical Disks",
                "Ports",
                "USB",
                "Printers",
                "Virtual Machine",
                "Cameras",
                "Network Information",
                "Shares",
                "Network Connections",
            ]},
            {"type": "note", "items": [
                "Anonimisering staat altijd aan. NVC maskeert serienummers, licentiesleutels, "
                "wachtwoorden en tokens, gebruikers- en computernamen, hostnamen, IP- en "
                "MAC-adressen, proxy-instellingen, UNC-paden en gebruikersprofielpaden. "
                "Controleer een rapport toch voordat u het deelt.",
                "Sommige waarden vereisen beheerdersrechten en tonen \"Vereist beheerder\" als "
                "NVC normaal draait. Klik met de rechtermuisknop op NVC en kies Als beheerder "
                "uitvoeren voor een volledig rapport.",
                "Stuurprogramma's, apparaten, netwerkverbindingen en processen zijn de trage "
                "verzamelaars op grote systemen.",
            ]},
        ],
    },
    {
        "id": "lossless-editor",
        "title": "Verliesvrije editor",
        "blocks": [
            {"type": "para", "text": (
                "Het tabblad Verliesvrije editor biedt FFmpeg-hulpmiddelen voor stream copy. "
                "Deze bewerkingen zijn snel omdat ze waar mogelijk opnieuw coderen vermijden. "
                "De uitvoercontainers zijn mp4, mkv, mov, avi en m4a; Audio uitpakken gebruikt "
                "altijd m4a.")},
            {"type": "figure", "fig_id": "FIG-06"},
            {"type": "table", "headers": ("Bewerking", "Wat het doet"), "rows": [
                ("Verliesvrij knippen",
                 "Knipt een deel tussen een begin- en eindtijdstip met stream copy."),
                ("Remuxen",
                 "Verpakt media opnieuw in mp4, mkv, mov of avi zonder opnieuw te coderen."),
                ("Audio uitpakken",
                 "Schrijft de eerste audiostream naar een m4a-bestand met alleen audio."),
                ("Audio verwijderen",
                 "Schrijft een stille kopie met alleen video."),
                ("Verliesvrij samenvoegen",
                 "Voegt compatibele clips samen met de concat-demuxer van FFmpeg."),
                ("Bestanden toevoegen",
                 "Voegt bronclips toe aan de samenvoeglijst."),
                ("Leegmaken",
                 "Verwijdert elke bronclip uit de samenvoeglijst."),
            ]},
            {"type": "note", "items": [
                "Verliesvrije bewerkingen vereisen compatibele codecs en containers. Als FFmpeg "
                "faalt, moeten de bronstreams mogelijk opnieuw worden gecodeerd, of is een "
                "andere uitvoercontainer nodig.",
                "Verliesvrij knippen kan alleen op een keyframe snijden, dus het werkelijke "
                "begin kan iets vroeger liggen dan het tijdstip dat u invoert.",
            ]},
        ],
    },
    {
        "id": "multi-source-recorder",
        "title": "Multibron-recorder",
        "blocks": [
            {"type": "para", "text": (
                "De Multibron-recorder neemt tot vier bronnen tegelijk op met FFmpeg. Het "
                "tabblad toont één rij per bron; configureer de bronnen in het dialoogvenster "
                "Video-instellingen.")},
            {"type": "figure", "fig_id": "FIG-07"},
            {"type": "para", "text": "Het recordertabblad"},
            {"type": "table", "headers": ("Bediening", "Wat het doet"), "rows": [
                ("Gebruiken", "Neemt deze rij op."),
                ("Videonaam", "Stelt het label in dat in de bestandsnaam wordt gebruikt."),
                ("Audionaam", "Stelt het audiolabel voor de rij in."),
                ("Dempen", "Neemt de rij zonder geluid op."),
                ("Volume", "Stelt het audioniveau in op 100, 75, 50, 25 of 0 %."),
                ("Codering", "copy behoudt de eigen gecomprimeerde video van de bron, alleen "
                 "voor RTSP-, stream- en bestandsbronnen. USB-camera's (DirectShow) en "
                 "schermopnamen worden altijd opnieuw gecodeerd met H.264, ongeacht de "
                 "gekozen Codering."),
                ("Uitvoermodus", "Losse video's schrijft één bestand per rij; Gecombineerd "
                 "raster schrijft één bestand met alle bronnen naast elkaar; Beeld-in-beeld "
                 "schrijft één bestand waarin bron 1 het beeld vult en de andere ingeschakelde "
                 "bronnen als inzetten linksonder staan, zoals het schema in de zijbalk "
                 "toont."),
                ("Bestandslocatie", "Stelt de opnamemap in. De standaard is uw map Video's."),
                ("Basisnaam bestand", "De standaard is Video. Losse video's, en Gecombineerd "
                 "raster of Beeld-in-beeld met één ingeschakelde bron, gebruiken "
                 "<basis>_<Videonaam>_<tijdstempel>.mp4. Gecombineerd raster en Beeld-in-beeld "
                 "met meer dan één ingeschakelde bron gebruiken "
                 "<basis>_Combined_<tijdstempel>.mp4."),
                ("Timer", 'Het veld toont "leeg = tot gestopt"; laat het leeg om op te nemen '
                 "tot u op Opname stoppen drukt."),
                ("Opnamelogboek tonen", "Opent het opnamelogboek."),
                ("Opname starten / Opname stoppen", "De knop in de voettekst start of stopt de opname."),
            ]},
            {"type": "para", "text": "Video-instellingen"},
            {"type": "figure", "fig_id": "FIG-09"},
            {"type": "steps", "items": [
                "Open Video-instellingen. Elke rij heeft Gebruiken, Videonaam, Videoapparaat, "
                "een knop voor camera-instellingen, Framesnelheid, Resolutie, Audionaam, "
                "Audioapparaat en Synchronisatieverschuiving.",
                "Kies bij Videoapparaat een USB-camera op de Windows-naam, kies RTSP/IP-camera "
                "en klik op de cameraknop om Adres / URL, Gebruikersnaam, Wachtwoord, Poort en "
                "Streampad in te voeren, of typ direct een rtsp://-, http://- of https://-URL, "
                "een bestandspad of een Basler/GenICam-brontekst. USB-apparaten vernieuwen... "
                "scant opnieuw. Het cameravenster weigert een Adres dat op een IP-adres lijkt "
                "maar het niet is (een getal boven 255, of drie of vijf getallen); als een "
                "opgeslagen adres fout is, toont de voorbeeldtegel \"Het camera-adres kan niet "
                "worden opgelost\" in plaats van opnieuw te verbinden -- open Video-instellingen "
                "en corrigeer het.",
                "Om het scherm op te nemen kiest u Schermopname bij Videoapparaat en klikt u "
                "op de cameraknop om Schermopname-instellingen te openen: het hele bureaublad "
                "(elk beeldscherm), één beeldscherm via de GPU, één venster gekozen uit een "
                "actuele lijst met open vensters, of een deel van het bureaublad ingevoerd als "
                "X, Y, breedte en hoogte of getekend met Op het scherm selecteren... (Escape "
                "annuleert). Het apparaatvak toont dan Schermopname (bureaublad | beeldscherm "
                "N, GPU | venster: titel | gebied X,Y BxH). Schermopnamen worden opgenomen met "
                "de framesnelheid van de rij (15 fps bij Auto), worden altijd gecodeerd naar "
                "H.264, tonen een voorbeeld zoals een netwerkstream en kunnen met camera's "
                "worden gecombineerd in Gecombineerd raster of Beeld-in-beeld.",
                "De standaardlijst Framesnelheid is 30.00, 25.00 en 15.00; de standaardlijst "
                "Resolutie is 1920 x 1080, 1280 x 720, 640 x 480 en Auto. Als een USB-camera is "
                "gekozen, vervangt NVC beide lijsten door de modi die het stuurprogramma meldt "
                "en voegt aan elke lijst Auto toe. Als de detectie mislukt, blijven de lijsten "
                "zoals ze waren: laat Resolutie op Auto en kies een framesnelheid die de camera "
                "ondersteunt. Auto wordt bij Framesnelheid alleen aangeboden na een geslaagde "
                "detectie.",
                "Kies per rij een Audioapparaat, of Geen audio. Lange apparaatnamen worden in "
                "de lijst ingekort om het venster smal te houden; houd de muis op het vak om de "
                "volledige naam te lezen. Apparaten vernieuwen scant microfoons opnieuw. Dempen "
                "of Volume 0 op het tabblad neemt die rij zonder geluid op.",
                "Synchronisatieverschuiving verschuift een bron eerder of later in een opname "
                "met Gecombineerd raster of Beeld-in-beeld, zodat clips die op iets "
                "verschillende momenten zijn gestart gelijk lopen.",
                "Vink Gebruik uit om een rij over te slaan -- elke rij, ook de eerste. Als geen "
                "rij in gebruik is, is de knop Start uitgeschakeld en meldt het tabblad "
                "\"Schakel minstens één bron in\". Toepassen houdt het venster open; OK past "
                "toe en sluit.",
            ]},
            {"type": "para", "text": "Voorinstellingen"},
            {"type": "steps", "items": [
                "Laden past de gekozen voorinstelling toe; Instellen overschrijft hem met de "
                "huidige instellingen; de kleine koppelingen Opslaan als... en Verwijderen maken "
                "een nieuwe of verwijderen hem. Een sterretje achter de naam markeert "
                "niet-opgeslagen wijzigingen.",
                "Voorinstellingen zijn JSON-bestanden onder "
                r"Public\Documents\Noldus\NVC\MediaRecorder\Presets.",
            ]},
            {"type": "para", "text": "Bediening vanaf de opdrachtregel"},
            {"type": "para", "text": (
                "Een ander programma kan een opname starten en stoppen door NVC.exe met een "
                "schakeloptie uit te voeren. De schakelopties zijn dezelfde letters die "
                "MRCmd.exe van MediaRecorder gebruikt, zodat vermeldingen in de lijst met "
                "externe toepassingen van The Observer XT kunnen worden hergebruikt met "
                "NVC.exe als programma. Als NVC al draait, wordt de schakeloptie eraan "
                "doorgegeven; zo niet, dan starten /E, /R, /C en /B NVC eerst, terwijl /S en /X "
                "niets doen.")},
            {"type": "table", "headers": ("Schakeloptie", "Wat het doet"), "rows": [
                ("/E", "Start NVC, of brengt het draaiende NVC naar voren."),
                ("/R", "Start een opname met de huidige recorderinstellingen."),
                ("/S", "Stopt de opname."),
                ("/X", "Stopt een eventuele opname en sluit NVC."),
                ("/C=naam", "Laadt de videovoorinstelling met die naam, of uit een .json-bestandspad."),
                ("/B=naam", "Stelt de basisnaam van het opnamebestand in."),
            ]},
            {"type": "steps", "items": [
                "Schakelopties zijn te combineren en worden altijd uitgevoerd in de volgorde "
                "voorinstelling, basisnaam, opnemen, stoppen, sluiten. Voorbeeld: "
                r"NVC.exe /E /C=Lab1 /B=Trial07 /R",
                "Zet een waarde met spaties tussen aanhalingstekens: NVC.exe \"/C=Two cameras\".",
                "Het proces sluit af met code 0 als het verzoek is geslaagd en 1 als dat niet "
                "zo is, bijvoorbeeld als NVC vergrendeld is, een conversie loopt of de "
                "voorinstelling niet bestaat. De reden wordt naar de console en het "
                "conversielogboek geschreven.",
            ]},
            {"type": "note", "items": [
                "Zonder microfoon behoudt een bestands- of RTSP-bron in h264-modus zijn eigen "
                "geluidsspoor; in copy-modus wordt een RTSP-bron zonder audio opgenomen; een "
                "USB-camera zonder microfoon is stil. Gecombineerd raster neemt zijn audio van "
                "de eerste ingeschakelde, niet-gedempte rij met een microfoon.",
                "Een opgeslagen microfoon die niet is aangesloten, wordt getoond als (niet "
                "gevonden). Als het audioapparaat faalt terwijl de opname start, herstart NVC "
                "die rij met alleen video en meldt dat in het opnamelogboek, zodat de "
                "camera-opname niet verloren gaat.",
                "FFmpeg heeft de exacte Windows-cameranaam nodig; sluit andere toepassingen die "
                "de camera mogelijk gebruiken.",
            ]},
        ],
    },
    {
        "id": "media-player",
        "title": "Mediaspeler",
        "blocks": [
            {"type": "para", "text": (
                "De Mediaspeler laadt tot vier clips voor gesynchroniseerd bekijken. Het "
                "tabblad is standaard verborgen; schakel het in via Instellingen -> "
                "Hulpmiddelen. Afspelen in Mediaspeler vanuit Geconverteerde bestanden toont "
                "het tabblad voor de huidige sessie, laadt het geselecteerde bestand en start "
                "het afspelen.")},
            {"type": "figure", "fig_id": "FIG-08"},
            {"type": "table", "headers": ("Bediening", "Wat het doet"), "rows": [
                ("Laden", "Laadt een clip in dat paneel."),
                ("Leegmaken", "Verwijdert de clip uit dat paneel."),
                ("Verschuiving (kolom in afspeellijst)", "Verschuift die clip in seconden ten opzichte van de gedeelde zoekpositie; dubbelklik op de cel om te bewerken."),
                ("Alles afspelen", "Speelt elk zichtbaar geladen paneel af en heet Alles pauzeren tijdens het afspelen."),
                ("Alles stoppen", "Stopt elk geladen paneel en zet de gedeelde positie terug op nul."),
                ("Opnieuw starten", "Gaat terug naar het begin en speelt elk zichtbaar geladen paneel af."),
                ("Zoekschuifregelaar", "Verplaatst elk zichtbaar geladen paneel op de gedeelde tijdlijn."),
                ("Snelheid", "Zet elk paneel op 0,25x, 0,5x, 1x, 1,5x of 2x afspelen."),
                ("Panelen", "Toont 1, 2 of 4 panelen."),
                ("Volume", "Stelt het volume voor elk paneel in van 0 tot 100."),
                ("Dempen", "Dempt elk paneel en heet Dempen opheffen zolang het gedempt is."),
                ("Volledig scherm", "Toont de panelen en de bedieningsbalk op volledig scherm; de panelen Inspecteren en Afspeellijst wijken tot u het volledig scherm verlaat."),
                ("Afspeellijst", "Toont of verbergt de afspeellijststrook onder de video; alle panelen delen één lijst."),
                ("Inspecteren", "Toont of verbergt het Inspecteren-paneel naast de video (zie Media-inspectie)."),
            ]},
            {"type": "para", "text": (
                "De uitlezing toont U:MM:SS.mmm / U:MM:SS.mmm · frame N / M. NVC leest de echte "
                "framesnelheid van de clip met FFprobe, zodat Links en Rechts precies één frame "
                "stappen. Framestappen pauzeert het afspelen.")},
            {"type": "table", "headers": ("Toetsen", "Actie"), "rows": [
                ("Spatie", "Afspelen of pauzeren"),
                ("Home", "Opnieuw starten vanaf het begin"),
                ("Links", "Eén frame terug"),
                ("Rechts", "Eén frame vooruit"),
                ("Shift+Links", "5 seconden terug"),
                ("Shift+Rechts", "5 seconden vooruit"),
                ("Omhoog", "Volume 5 omhoog"),
                ("Omlaag", "Volume 5 omlaag"),
                ("M", "Dempen of dempen opheffen"),
                ("F", "Volledig scherm in- of uitschakelen"),
                ("Escape", "Volledig scherm verlaten"),
                ("N", "Volgend item in de afspeellijst"),
                ("P", "Vorig item in de afspeellijst"),
            ]},
            {"type": "para", "text": (
                "Sneltoetsen werken zolang het tabblad Mediaspeler de focus heeft. Druk op F, "
                "klik op Volledig scherm of dubbelklik op een paneel om naar volledig scherm te "
                "gaan. De bedieningsbalk verbergt zich drie seconden nadat de muis stopt met "
                "bewegen en komt terug als de muis beweegt. Druk op Escape of F, of dubbelklik, "
                "om het volledig scherm te verlaten.")},
            {"type": "para", "text": (
                "De bedieningsbalk zit onder de zoekschuifregelaar in drie groepen van links: "
                "Afspelen, Stoppen en Opnieuw starten; Volledig scherm, Afspeellijst en "
                "Inspecteren; dan Panelen, Snelheid, Volume en Dempen. Onder elke tegel noemt "
                "een bijschrift de clip, in het midden ingekort als de naam lang is (houd de "
                "muis erop voor de volledige naam).")},
            {"type": "para", "text": (
                "Een clip in een paneel laden -- door slepen, de knop Laden of de afspeellijst "
                "-- selecteert dat paneel ook: de afspeellijst markeert die clip en het "
                "Inspecteren-paneel toont de gegevens ervan, zodat een bestand dat op het "
                "tweede paneel wordt neergezet meteen zichtbaar is.")},
            {"type": "para", "text": (
                "Afspeellijst opent een strook onder de video met Bestanden toevoegen..., Map "
                "toevoegen..., Verwijderen en Leegmaken. Er is één lijst voor het hele tabblad: "
                "elke clip die u laadt of op een paneel neerzet, wordt eraan toegevoegd, zodat "
                "de strook alles toont wat de speler heeft gezien. De strook heeft de kolommen "
                "Bestandsnaam, Paneel en Verschuiving; Paneel vermeldt de panelen die de clip nu "
                "tonen en verschijnt alleen als er meer dan één paneel op het scherm staat. "
                "Dubbelklik op een rij om hem in het geselecteerde paneel te laden. Een rij "
                "markeren toont de gegevens van die clip in het Inspecteren-paneel zonder hem te "
                "laden; op een paneel klikken doet hetzelfde voor zijn clip. Sleep rijen om ze "
                "te herordenen, of zet bestanden uit de Verkenner in de strook neer. N en P "
                "lopen met het geselecteerde paneel door de lijst. Met Panelen op 1 start het "
                "volgende item automatisch als een clip eindigt. In de compacte modus blijft de "
                "strook enkele rijen hoog en scrolt hij zelf.")},
            {"type": "para", "text": (
                "Verschuiving is een synchronisatieverschuiving per clip in seconden: een "
                "negatieve waarde speelt die clip eerder dan de andere, een positieve later, "
                "zodat opnamen van hetzelfde moment van twee camera's gelijk lopen. Dubbelklik "
                "op de cel Verschuiving en typ of stap de waarde; een gepauzeerd paneel gaat "
                "meteen naar de nieuwe positie.")},
            {"type": "para", "text": (
                "Een clip toont zijn eerste frame zodra hij is geladen of op een paneel is "
                "neergezet (de tegel toont even Laden...), en de zoekschuifregelaar verplaatst "
                "het beeld nog voordat u op Afspelen drukt. Het zijbalkvoorbeeld links volgt de "
                "clip van het geselecteerde paneel.")},
            {"type": "note", "items": [
                'Een bestand dat Windows niet kan decoderen toont "Windows kan dit bestand niet '
                'afspelen." of noemt de codec en container, met "Converteren naar MP4 (H.264) '
                'en afspelen". De geconverteerde kopie wordt met een unieke naam naar uw '
                "Doelmap geschreven en daarna geladen.",
                "NVC onthoudt tussen sessies de laatste map, het aantal panelen, het volume, "
                "dempen en of de panelen Inspecteren en Afspeellijst open stonden.",
                "Het afspelen gebruikt Windows Media Foundation. MP4-, MOV-, MKV-, AVI- en "
                "WMV-bestanden met gangbare codecs spelen direct; gebruik het conversieaanbod "
                "voor al het andere.",
            ]},
        ],
    },
    {
        "id": "language",
        "title": "Taal",
        "blocks": [
            {"type": "para", "text": (
                "Menu -- Taal vermeldt English, Nederlands en Vereenvoudigd Chinees; het "
                "laatste item verschijnt in het menu in Chinese tekens. NVC slaat de keuze op "
                "en zegt \"NVC toont <taal> de volgende keer dat het start.\" De Handleiding en "
                "de Snelstartgids bestaan in alle drie de talen; Menu -- Help opent de "
                "handleiding voor de gekozen taal en valt terug op Engels als dat bestand "
                "ontbreekt.")},
        ],
    },
    {
        "id": "updates-and-logs",
        "title": "Updates en logboeken",
        "blocks": [
            {"type": "table", "headers": ("Onderdeel", "Waar / wat"), "rows": [
                ("Controleren op updates",
                 "Open het via het menu. Een build zonder update-adres antwoordt \"Updates niet "
                 "geconfigureerd\". Als een adres is geconfigureerd en er een nieuwere versie "
                 "bestaat, verschijnt \"Update v<versie> beschikbaar!\" in de zijbalk."),
                ("Logbestand",
                 r"Het roterende toepassingslogboek, conversion_log.txt, staat onder "
                 r"%APPDATA%\NVC\logs. Elke conversie heeft een logboek <naam "
                 r"uitvoerbestand>.txt in dezelfde map, of in de Logboekmap die onder "
                 r"Instellingen -- Mappen is gekozen."),
                ("NVC_LOG_LEVEL",
                 "Zet deze omgevingsvariabele op DEBUG om volledige tracebacks vast te leggen."),
                ("Instellingenbestand", r"%APPDATA%\NVC\config.json."),
                ("Standaard mediamappen",
                 r"Public\Documents\Noldus\NVC\Source, "
                 r"Public\Documents\Noldus\NVC\Destination en "
                 r"Public\Documents\Noldus\NVC\Backup."),
                ("Recordervoorinstellingen",
                 r"Public\Documents\Noldus\NVC\MediaRecorder\Presets."),
            ]},
        ],
    },
    {
        "id": "troubleshooting",
        "title": "Problemen oplossen",
        "blocks": [
            {"type": "table", "headers": ("Probleem", "Wat u kunt proberen"), "rows": [
                ("FFmpeg of FFprobe ontbreekt",
                 "Zorg dat ffmpeg.exe en ffprobe.exe naast de programmabestanden staan."),
                ("Conversie mislukt meteen",
                 "Controleer het conversielogboek. Ongeldige combinaties van codec en container, "
                 "en aangepaste FFmpeg-vlaggen, zijn de gebruikelijke oorzaken."),
                ("Uitvoerbestand bestaat al",
                 "NVC maakt automatisch een genummerde bestandsnaam. Zoek in de doelmap naar "
                 "(1), (2), enzovoort."),
                ("GPU-optie werkt niet",
                 "Werk uw GPU-stuurprogramma's bij, controleer of FFmpeg uw encoder ondersteunt, "
                 "of schakel GPU-codering uit om terug te vallen op de CPU."),
                ("App lijkt inactief na het neerzetten van een bestand",
                 "Controleer of de app ontgrendeld is, het bewaken is gestart en de "
                 "bestandsextensie wordt ondersteund."),
                ("PC-rapport is traag",
                 "Stuurprogramma's, apparaten, netwerkverbindingen en processen zijn de trage "
                 "verzamelaars op grote systemen. Laat ze afronden."),
                ("Camera: Could not find video device",
                 "FFmpeg heeft de exacte Windows-cameranaam nodig. Kies hem uit de lijst "
                 "Videoapparaat in plaats van hem te typen, en sluit andere toepassingen die de "
                 "camera vasthouden."),
                ("Microfoon toont (niet gevonden)",
                 "De opgeslagen microfoon is niet aangesloten. Sluit hem aan en klik op "
                 "Apparaten vernieuwen, of kies een ander apparaat of Geen audio."),
                ("Opname heeft geen geluid",
                 "Controleer Dempen en Volume op het tabblad en het Audioapparaat in "
                 "Video-instellingen. Als het audioapparaat bij de start faalde, heeft NVC "
                 "alleen video opgenomen en meldt het dat in het opnamelogboek."),
                ("Mediaspeler zegt dat Windows dit bestand niet kan afspelen",
                 "De codec of container wordt niet ondersteund door Windows Media Foundation. "
                 "Klik op Converteren naar MP4 (H.264) en afspelen."),
                ("Een tabblad ontbreekt",
                 "Open Instellingen, tabblad Hulpmiddelen, en vink het aan."),
                ("Helpmenu zegt dat het document niet is gevonden",
                 "De gegenereerde handleiding moet in docs/help, een map help of naast het "
                 "uitvoerbare bestand staan. Bouw hem opnieuw met python "
                 "docs/help/source/build_help_docs.py."),
                ("Iets is mislukt zonder melding",
                 "Zet de omgevingsvariabele NVC_LOG_LEVEL op DEBUG en reproduceer het probleem. "
                 "NVC legt dan de volledige traceback vast voor fouten die het anders stil "
                 "afhandelt."),
            ]},
            {"type": "para", "text": (
                r"NVC bewaart logboeken onder %APPDATA%\NVC\logs: conversion_log.txt is het "
                "roterende toepassingslogboek, en elke conversie heeft een logboek <naam "
                "uitvoerbestand>.txt dat Geconverteerde bestanden -- Logbestand openen opent "
                "(conversielogboeken gaan naar de Logboekmap als die onder Instellingen -- "
                "Mappen is ingesteld).")},
        ],
    },
    {
        "id": "best-practices",
        "title": "Aanbevolen werkwijzen",
        "blocks": [
            {"type": "steps", "items": [
                "Gebruik een aparte bronmap en doelmap.",
                "Bewaar originelen totdat u hebt bevestigd dat de geconverteerde bestanden goed "
                "afspelen.",
                "Gebruik MP4 met H.264 en AAC voor de breedste compatibiliteit.",
                "Gebruik HEVC alleen als kleinere bestanden belangrijk zijn en de doelspelers "
                "het ondersteunen.",
                "Controleer PC-rapporten voordat u ze deelt.",
                "Houd aangepaste FFmpeg-vlaggen eenvoudig en test ze eerst op een klein bestand.",
                "Sla voor elke camera-opstelling een recordervoorinstelling op, zodat een sessie "
                "met één klik op Laden begint.",
                "Bekijk opnamen met Panelen op 1 als u wilt dat de afspeellijst automatisch "
                "doorgaat.",
            ]},
        ],
    },
    {
        "id": "faq",
        "title": "Veelgestelde vragen",
        "blocks": [
            {"type": "table", "headers": ("Vraag", "Antwoord"), "rows": [
                ("Overschrijft NVC mijn geconverteerde video's?",
                 "Nee. NVC maakt een genummerde bestandsnaam als een uitvoer al bestaat."),
                ("Kan ik bestanden converteren terwijl het bewaken is gestopt?",
                 "Neergezette bestanden kunnen in de wachtrij komen en worden verwerkt zodra het "
                 "bewaken start, afhankelijk van waar ze zijn neergezet. Bestanden kunnen ook "
                 "geforceerd worden geconverteerd via de sleep-en-neerzetpaden die voor "
                 "handmatige conversie bedoeld zijn."),
                ("Waarom speelde mijn HEVC-bestand ergens niet af?",
                 "HEVC is efficiënt maar minder universeel ondersteund dan H.264. Gebruik H.264 "
                 "als compatibiliteit belangrijk is."),
                ("Waar worden logboeken opgeslagen?",
                 r"Standaard onder %APPDATA%\NVC\logs: conversion_log.txt is het "
                 "roterende toepassingslogboek, met één logboek <naam uitvoerbestand>.txt per "
                 "conversie. Instellingen -- Mappen -- Logboekmap verplaatst de "
                 "conversielogboeken naar een andere map."),
                ("Kan ik twee exemplaren van NVC tegelijk draaien?",
                 "Nee. NVC staat één exemplaar toe, zodat twee exemplaren niet dezelfde bronmap "
                 "kunnen verwerken."),
                ("Waar komen opnamen terecht?",
                 "In de Bestandslocatie op het recordertabblad, standaard uw map Video's, met de "
                 "naam <basis>_<Videonaam>_<tijdstempel>.mp4 of "
                 "<basis>_Combined_<tijdstempel>.mp4."),
                ("Waarom speelt mijn MKV niet in de Mediaspeler?",
                 "Windows Media Foundation decodeert niet elke codec. Gebruik Converteren naar "
                 "MP4 (H.264) en afspelen; de kopie gaat naar uw Doelmap."),
                ("Kan ik opnemen zonder microfoon?",
                 "Ja. Kies Geen audio, of demp de rij. Een bestands- of RTSP-bron in h264-modus "
                 "behoudt zijn eigen geluidsspoor."),
                ("Waarom zegt het PC-rapport Vereist beheerder?",
                 "Sommige Windows-gegevens zijn alleen leesbaar met verhoogde rechten. Voer NVC "
                 "als beheerder uit voor een volledig rapport; anonimisering blijft van "
                 "toepassing."),
            ]},
        ],
    },
]
