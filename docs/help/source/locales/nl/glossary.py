"""Dutch glossary. Term keys stay in English (see locales/en/glossary.py)."""
from __future__ import annotations

GLOSSARY_TITLE = "Verklarende woordenlijst"

GLOSSARY_INTRO = (
    "Termen die in deze handleiding worden gebruikt. FFmpeg-terminologie is "
    "behouden waar u die ook in het conversielogboek tegenkomt."
)

GLOSSARY_HEADERS = ("Term", "Betekenis")

GLOSSARY_ROWS: list[tuple[str, str]] = [
    ("Container",
     "De bestandsomhulling die video- en audiostreams bevat, zoals MP4, MKV of "
     "AVI. De container is wat de bestandsextensie aangeeft; hij staat los van "
     "de codec die erin wordt gebruikt."),
    ("Codec",
     "De methode waarmee een stream wordt gecomprimeerd. H.264 (libx264) en HEVC "
     "(libx265) zijn videocodecs; AAC en MP3 zijn audiocodecs."),
    ("FFmpeg",
     "Het opdrachtregelprogramma dat NVC uitvoert om de eigenlijke conversie te "
     "doen. De uitvoer ervan verschijnt in het conversielogboek."),
    ("FFprobe",
     "Het inspectiehulpmiddel van FFmpeg. NVC gebruikt het om duur, streams, codecs "
     "en andere metadata te lezen zonder iets te converteren."),
    ("Stream copy",
     "Media in een nieuwe container schrijven zonder opnieuw te coderen. Snel en "
     "verliesvrij, maar alleen mogelijk als de doelcontainer de bestaande streams "
     "ondersteunt. Ook remuxen genoemd."),
    ("Remux",
     "De container van een bestand wijzigen terwijl de streams onaangeroerd "
     "blijven. Zie stream copy."),
    ("Transcode",
     "Een stream decoderen en opnieuw coderen, wat de kwaliteit verandert en "
     "aanzienlijk langer duurt dan een stream copy."),
    ("Keyframe",
     "Een frame dat volledig is opgeslagen in plaats van als verschil met zijn "
     "buren. Zoeken en verliesvrij knippen kunnen alleen precies op een keyframe "
     "uitkomen."),
    ("GOP",
     "Group of Pictures: het interval tussen keyframes. Een kortere GOP maakt "
     "scrubben preciezer, ten koste van de bestandsgrootte."),
    ("Bitrate",
     "Gegevens per seconde media, meestal in kbps of Mbps. Een hogere bitrate "
     "betekent doorgaans betere kwaliteit en een groter bestand."),
    ("GPU encoding",
     "Speciale videohardware (NVENC bij NVIDIA, AMF bij AMD, Quick Sync bij Intel) "
     "gebruiken om te coderen in plaats van de CPU. Veel sneller; de "
     "codec-ondersteuning hangt af van uw stuurprogramma's."),
    ("DirectShow",
     "De Windows-opname-interface die NVC gebruikt om van lokale apparaten op te "
     "nemen. Bronnen worden geschreven als video=Apparaatnaam."),
    ("Media Foundation",
     "Het Windows-afspeelraamwerk dat de Mediaspeler gebruikt om ondersteunde "
     "media te decoderen en af te spelen."),
    ("RTSP",
     "Een streamingprotocol dat door de meeste IP- en netwerkcamera's wordt "
     "gebruikt. Bronnen worden geschreven als URL, zoals rtsp://192.168.1.10/stream."),
    ("GenICam",
     "De generieke camera-interface van Basler en andere industriële camera's. "
     "Configureer deze camera's in Basler pylon Viewer."),
    ("Preset",
     "Een opgeslagen recorderconfiguratie, bewaard als JSON onder "
     r"Public\Documents\Noldus\NVC\MediaRecorder\Presets."),
    ("Sync offset",
     "Een tijdcorrectie die één bron eerder of later verschuift in een opname met "
     "Gecombineerd raster of Beeld-in-beeld, zodat de bronnen gelijk lopen."),
    ("Picture-in-picture",
     "Een uitvoermodus van de recorder: bron 1 vult het beeld en de andere "
     "ingeschakelde bronnen verschijnen als kleine inzetten linksonder, in één "
     "bestand."),
    ("Screen capture",
     "Een brontype van de recorder dat het hele bureaublad, één beeldscherm, één "
     "venster of een deel van het scherm opneemt in plaats van een camera."),
    ("Frame step",
     "Precies één frame vooruit of achteruit gaan op basis van de framesnelheid "
     "van de clip."),
    ("Playlist",
     "Een geordende lijst mediabestanden voor één paneel van de Mediaspeler. Met "
     "één paneel start het volgende item automatisch."),
    ("Administrator (elevation)",
     "NVC uitvoeren met beheerdersrechten zodat het PC-rapport beveiligde "
     "Windows-gegevens kan lezen."),
    ("Tool tab",
     "Een tabblad in het hoofdvenster dat kan worden verborgen of getoond via "
     "Instellingen -- Hulpmiddelen."),
    ("Retention period",
     "Hoe lang NVC een origineel bestand na een geslaagde conversie bewaart "
     "voordat het wordt verwijderd. Wachtende verwijderingen overleven een "
     "herstart."),
    ("Redaction",
     "Het altijd ingeschakelde maskeren van gevoelige waarden zoals licentiesleutels, "
     "serienummers, MAC-adressen en gebruikerspaden in een PC-rapport voordat het "
     "wordt gedeeld."),
]
