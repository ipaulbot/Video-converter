"""Dutch content for the Quick Start Guide. Mirrors locales/en/quickstart.py block for block."""
from __future__ import annotations

CHAPTERS: list[dict] = [
    {
        "id": "before-you-start",
        "title": "Voordat u begint",
        "blocks": [
            {"type": "para", "text": (
                "NVC converteert video met FFmpeg. Het heeft twee dingen nodig voordat het iets "
                "kan doen: een bronmap om te bewaken en een doelmap om naar te schrijven.")},
            {"type": "note", "items": [
                "ffmpeg.exe en ffprobe.exe moeten naast de programmabestanden staan. NVC meldt "
                "bij het opstarten dat ze ontbreken als ze er niet zijn.",
            ]},
            {"type": "figure", "fig_id": "FIG-00"},
        ],
    },
    {
        "id": "first-conversion",
        "title": "Uw eerste conversie",
        "blocks": [
            {"type": "steps", "items": [
                "Open Instellingen via het menu.",
                "Stel een Bronmap in -- de map die NVC bewaakt op nieuwe video.",
                "Stel een Doelmap in -- waar geconverteerde video wordt geschreven.",
                "Laat het uitvoerformaat op MP4 en de codecs op hun standaardwaarden. Die "
                "passen bij bijna elke situatie.",
                "Sluit Instellingen en klik op Start.",
                "Kopieer een video naar de bronmap. NVC zet hem in de wachtrij en converteert "
                "hem automatisch.",
            ]},
            {"type": "figure", "fig_id": "FIG-01"},
            {"type": "para", "text": (
                "De voortgang verschijnt in het conversielogboek. Als de taak klaar is, legt "
                "de tabel Geconverteerde bestanden het resultaat vast.")},
        ],
    },
    {
        "id": "record-a-webcam",
        "title": "Opnemen met een webcam",
        "blocks": [
            {"type": "para", "text": (
                "De Multibron-recorder neemt tot vier camera's of streams op. Eén USB-webcam "
                "is het eenvoudigste geval.")},
            {"type": "steps", "items": [
                "Open het tabblad Multibron-recorder en klik op Video-instellingen.",
                "Open in rij 1 de lijst Videoapparaat en kies uw camera op de Windows-naam. "
                "Ontbreekt hij, kies dan USB-apparaten vernieuwen...",
                "Kies een microfoon bij Audioapparaat, of Geen audio. Laat Framesnelheid en "
                "Resolutie op de gedetecteerde waarden. Als de detectie is mislukt, laat "
                "Resolutie dan op Auto en kies een framesnelheid die de camera ondersteunt.",
                "Klik op OK. Kies terug op het tabblad Losse video's en een Bestandslocatie.",
                "Laat Timer leeg en klik op Opname starten in de voettekst. Klik op Opname "
                "stoppen als u klaar bent.",
            ]},
            {"type": "para", "text": (
                "Het bestand wordt naar de Bestandslocatie geschreven als "
                "Video_<Videonaam>_<tijdstempel>.mp4. Gebruik in Video-instellingen Opslaan "
                "als... om de opstelling als voorinstelling te bewaren, zodat de volgende "
                "sessie één klik op Laden kost.")},
        ],
    },
    {
        "id": "review-a-recording",
        "title": "Een opname bekijken",
        "blocks": [
            {"type": "steps", "items": [
                "Selecteer in Geconverteerde bestanden een bestand en klik op Afspelen, of "
                "klik er met de rechtermuisknop op en kies Afspelen in Mediaspeler. U kunt ook "
                "het tabblad Mediaspeler openen en op Laden klikken bij een paneel.",
                "Druk op Spatie om af te spelen of te pauzeren, Links en Rechts om één frame "
                "te stappen, Shift+Links en Shift+Rechts om 5 seconden te springen.",
                "Druk op F voor volledig scherm en op Escape om terug te keren.",
                "Zet Panelen op 1, 2 of 4. Gebruik 2 of 4 om opnamen naast elkaar te "
                "vergelijken; elk paneel heeft zijn eigen verschuiving om clips gelijk te "
                "zetten die op verschillende momenten zijn gestart.",
            ]},
            {"type": "note", "items": [
                "Het tabblad Mediaspeler is standaard verborgen. Afspelen in Mediaspeler toont "
                "het voor deze sessie; vink het aan in Instellingen, tabblad Hulpmiddelen, om "
                "het te behouden.",
            ]},
        ],
    },
    {
        "id": "safe-defaults",
        "title": "Instellingen die de moeite waard zijn",
        "blocks": [
            {"type": "table", "headers": ("Instelling", "Begin met"), "rows": [
                ("Uitvoerformaat", "MP4. De breedst afspeelbare container."),
                ("Videocodec", "libx264. Speelt vrijwel overal."),
                ("Audiocodec", "AAC. De standaardpartner van MP4."),
                ("Videobitrate", "Auto, tenzij u op een bepaalde bestandsgrootte mikt."),
                ("Videoformaat", "Auto, om de oorspronkelijke afmetingen te behouden."),
                ("Originele bestanden", "Originelen bewaren, totdat u de uitvoer vertrouwt."),
            ]},
            {"type": "note", "items": [
                "NVC overschrijft nooit een bestaande uitvoer. Een tweede conversie van "
                "video.mp4 wordt video (1).mp4, precies zoals een herhaalde browserdownload.",
            ]},
        ],
    },
    {
        "id": "if-something-goes-wrong",
        "title": "Als er iets misgaat",
        "blocks": [
            {"type": "steps", "items": [
                "Lees eerst het conversielogboek. FFmpeg zegt meestal precies waar het over "
                "struikelde.",
                "Controleer of de app ontgrendeld is en of het bewaken is gestart.",
                "Controleer of de bestandsextensie er een is die NVC ondersteunt.",
                "Staat GPU-codering aan, zet die dan uit en probeer het opnieuw op de CPU.",
                "Zet bij een fout zonder enige melding de omgevingsvariabele NVC_LOG_LEVEL op "
                "DEBUG en reproduceer de fout. NVC logt dan de volledige traceback.",
            ]},
            {"type": "para", "text": (
                "De Handleiding behandelt elk tabblad en elke instelling volledig, inclusief "
                "de Verliesvrije editor, de Multibron-recorder en het hulpmiddel PC-rapport.")},
        ],
    },
]
