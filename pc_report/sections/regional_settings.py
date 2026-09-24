"""Regional Settings: locales, time zone, formats with live samples, and installed input languages."""
from __future__ import annotations

from .. import decode
from ..section import Section, first_dict, kv_groups, list_table, rows_of, sub_heading

SCRIPT = r"""
$c = Get-Culture; $ui = Get-UICulture; $sys = Get-WinSystemLocale -ErrorAction SilentlyContinue
$loc = Get-WinHomeLocation -ErrorAction SilentlyContinue; $tz = Get-TimeZone
$intl = Get-ItemProperty 'HKCU:\Control Panel\International' -ErrorAction SilentlyContinue
$langs = @(Get-WinUserLanguageList -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ Tag = $_.LanguageTag; Name = $_.EnglishName; Autonym = $_.Autonym; InputMethods = ($_.InputMethodTips -join ', ') } })
$now = Get-Date
[pscustomobject]@{
  Culture = $c.Name; CultureDisplay = $c.DisplayName; UICulture = $ui.Name; UICultureDisplay = $ui.DisplayName
  SystemLocale = [string]$sys.Name; SystemLocaleDisplay = [string]$sys.DisplayName
  HomeLocation = [string]$loc.HomeLocation; GeoId = $loc.GeoId
  TimeZoneId = $tz.Id; TimeZoneDisplay = $tz.DisplayName; BaseUtcOffset = [string]$tz.BaseUtcOffset
  SupportsDst = $tz.SupportsDaylightSavingTime; IsDst = [System.TimeZoneInfo]::Local.IsDaylightSavingTime($now)
  ShortDate = $intl.sShortDate; LongDate = $intl.sLongDate; ShortTime = $intl.sShortTime; TimeFormat = $intl.sTimeFormat
  Decimal = $intl.sDecimal; Thousand = $intl.sThousand; ListSeparator = $intl.sList; Currency = $intl.sCurrency
  Measure = $intl.iMeasure; FirstDayOfWeek = $intl.iFirstDayOfWeek; CalendarType = $intl.iCalendarType
  NativeDigits = $intl.sNativeDigits; NegativeSign = $intl.sNegativeSign
  DateSample = $now.ToString('d'); LongDateSample = $now.ToString('D'); TimeSample = $now.ToString('T')
  NumberSample = (1234567.89).ToString('N2'); CurrencySample = (1234.5).ToString('C')
  Languages = $langs
}
"""

MEASURE = {0: "Metric", 1: "U.S."}
DAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
CALENDARS = {1: "Gregorian (localized)", 2: "Gregorian (English)", 3: "Japanese Emperor Era", 4: "Taiwan",
             5: "Korean Tangun Era", 6: "Hijri", 7: "Thai", 8: "Hebrew", 9: "Gregorian Middle East French",
             10: "Gregorian Arabic", 11: "Gregorian Transliterated English", 12: "Gregorian Transliterated French",
             23: "Um Al Qura"}
LANG_COLUMNS = [("Tag", "Tag"), ("Name", "Language"), ("Autonym", "Native name"), ("Keyboard Layouts", "Keyboard Layouts")]


def _pair(display, code):
    return f"{display} [{code}]" if display and code else (display or code or "")


def build(raw: dict) -> dict:
    raw = raw or {}
    dst = ""
    if raw.get("SupportsDst") is not None:
        dst = "Supported" if raw.get("SupportsDst") else "Not supported"
        if raw.get("SupportsDst"):
            dst += ", currently active" if raw.get("IsDst") else ", not active"
    locales = {
        "User Locale": _pair(raw.get("CultureDisplay"), raw.get("Culture")),
        "Display Language": _pair(raw.get("UICultureDisplay"), raw.get("UICulture")),
        "System Locale": _pair(raw.get("SystemLocaleDisplay"), raw.get("SystemLocale")),
        "Home Location": f"{raw.get('HomeLocation', '')} (GeoID {raw.get('GeoId')})" if raw.get("GeoId") else raw.get("HomeLocation", ""),
    }
    time = {
        "Time Zone": raw.get("TimeZoneDisplay", ""), "Time Zone ID": raw.get("TimeZoneId", ""),
        "UTC Offset": raw.get("BaseUtcOffset", ""), "Daylight Saving Time": dst,
    }
    formats = {
        "Short Date": raw.get("ShortDate", ""), "Short Date Sample": raw.get("DateSample", ""),
        "Long Date": raw.get("LongDate", ""), "Long Date Sample": raw.get("LongDateSample", ""),
        "Short Time": raw.get("ShortTime", ""), "Time Format": raw.get("TimeFormat", ""), "Time Sample": raw.get("TimeSample", ""),
        "Decimal Symbol": raw.get("Decimal", ""), "Digit Grouping Symbol": raw.get("Thousand", ""),
        "List Separator": raw.get("ListSeparator", ""), "Negative Sign": raw.get("NegativeSign", ""),
        "Native Digits": raw.get("NativeDigits", ""), "Number Sample": raw.get("NumberSample", ""),
        "Currency Symbol": raw.get("Currency", ""), "Currency Sample": raw.get("CurrencySample", ""),
        "Measurement System": decode.lookup(MEASURE, raw.get("Measure")),
        "First Day of Week": decode.lookup(DAYS, raw.get("FirstDayOfWeek")),
        "Calendar": decode.lookup(CALENDARS, raw.get("CalendarType")),
    }
    languages = [{"Tag": lang.get("Tag", ""), "Name": lang.get("Name", ""), "Autonym": lang.get("Autonym", ""),
                  "Keyboard Layouts": lang.get("InputMethods", "")} for lang in rows_of(raw.get("Languages"))]
    return {"groups": [{"title": "Locales", "rows": locales}, {"title": "Time", "rows": time},
                       {"title": "Formats", "rows": formats}], "languages": languages}


def collect(ctx):
    return build(first_dict(ctx.query("regional", SCRIPT)))


def render(data, ctx):
    data = data if isinstance(data, dict) else {}
    return kv_groups(data.get("groups")) + sub_heading("Input languages") + list_table(LANG_COLUMNS, data.get("languages"))


SECTION = Section(key="regional_settings", title="Regional Settings", group="Software", collect=collect, render=render)
