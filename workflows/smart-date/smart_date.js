#!/usr/bin/osascript -l JavaScript
ObjC.import('Foundation');

function run(argv) {
    var query = argv[0];

    if (!query || query.length < 2) {
        return JSON.stringify({
            items: [{
                title: "Enter a date or time",
                subtitle: "e.g., 'next tuesday', 'in three hours', 'march 15'",
                valid: false
            }]
        });
    }

    // Normalize word numbers to digits and rewrite patterns for broader parsing
    var normalized = normalizeQuery(query);

    // Try NSDataDetector first (handles named days, specific dates, "in N days/weeks")
    var detector = $.NSDataDetector.dataDetectorWithTypesError($.NSTextCheckingTypeDate, $());
    var nsQuery = $(normalized);
    var range = $.NSMakeRange(0, nsQuery.length);
    var matches = detector.matchesInStringOptionsRange(nsQuery, 0, range);

    var date = null;
    if (matches.count > 0) {
        date = matches.objectAtIndex(0).date;
    } else {
        // Fallback: handles hours, minutes, months, years, "ago", word numbers
        date = parseRelativeTime(normalized);
    }

    if (!date) {
        return JSON.stringify({
            items: [{
                title: "Date not recognized",
                subtitle: "Try: 'next friday', 'two days ago', 'in three months'",
                valid: false
            }]
        });
    }

    var unix = Math.floor(date.timeIntervalSince1970);
    var hasTime = detectTimeComponent(normalized);
    var items = hasTime ? formatDateTime(date, unix) : formatDateOnly(date, unix);
    return JSON.stringify({ items: items });
}

function normalizeQuery(query) {
    var q = query.toLowerCase();
    var words = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14',
        'fifteen': '15', 'sixteen': '16', 'seventeen': '17', 'eighteen': '18',
        'nineteen': '19', 'twenty': '20', 'thirty': '30'
    };
    for (var word in words) {
        q = q.replace(new RegExp('\\b' + word + '\\b', 'g'), words[word]);
    }
    // "half an hour" -> "30 minutes"
    q = q.replace(/\bhalf\s+an?\s+hour\b/g, '30 minutes');
    // "a week/month/year" -> "1 week/month/year"
    q = q.replace(/\ban?\s+(second|minute|hour|day|week|month|year)/g, '1 $1');
    // "next month/year" -> "in 1 month/year"
    q = q.replace(/\bnext\s+(month|year)\b/g, 'in 1 $1');
    // "last month/year" -> "1 month/year ago"
    q = q.replace(/\blast\s+(month|year)\b/g, '1 $1 ago');
    return q;
}

function parseRelativeTime(query) {
    var match = query.match(/(?:in\s+)?(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)(?:\s+(?:from\s+now|ago))?/i);
    if (!match) return null;
    var amount = parseInt(match[1]);
    var unit = match[2].toLowerCase();
    var isPast = /\bago\b/i.test(query);
    if (isPast) amount = -amount;

    // Sub-day and day/week: simple time interval arithmetic
    if (/^(s|sec)/.test(unit)) return $.NSDate.date.dateByAddingTimeInterval(amount);
    if (/^(mi|min)/.test(unit)) return $.NSDate.date.dateByAddingTimeInterval(amount * 60);
    if (/^(h|hr)/.test(unit)) return $.NSDate.date.dateByAddingTimeInterval(amount * 3600);
    if (/^d/.test(unit)) return $.NSDate.date.dateByAddingTimeInterval(amount * 86400);
    if (/^w/.test(unit)) return $.NSDate.date.dateByAddingTimeInterval(amount * 604800);

    // Months and years: use NSCalendar for proper calendar arithmetic
    var cal = $.NSCalendar.currentCalendar;
    var comp = $.NSDateComponents.alloc.init;
    if (/^mo/.test(unit)) comp.month = amount;
    else if (/^y/.test(unit)) comp.year = amount;
    return cal.dateByAddingComponentsToDateOptions(comp, $.NSDate.date, 0);
}

function detectTimeComponent(query) {
    if (/\d{1,2}:\d{2}/.test(query)) return true;
    if (/\d{1,2}\s*(am|pm)/i.test(query)) return true;
    if (/\bat\s+\d/i.test(query)) return true;
    if (/(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b/i.test(query)) return true;
    return false;
}

function fmt(date, template, localeId) {
    var f = $.NSDateFormatter.alloc.init;
    f.locale = $.NSLocale.alloc.initWithLocaleIdentifier(localeId);
    f.dateFormat = template;
    return f.stringFromDate(date).js;
}

function fmtStyle(date, localeId, dateStyle, timeStyle) {
    var f = $.NSDateFormatter.alloc.init;
    f.locale = $.NSLocale.alloc.initWithLocaleIdentifier(localeId);
    f.dateStyle = dateStyle;
    f.timeStyle = timeStyle;
    return f.stringFromDate(date).js;
}

function item(value, label) {
    return {
        title: value,
        subtitle: label,
        arg: value,
        text: { copy: value, largetype: value }
    };
}

function formatDateOnly(date, unix) {
    return [
        item(fmt(date, "yyyy-MM-dd", "en_US_POSIX"), "ISO Date"),
        item(fmt(date, "dd.MM.yyyy", "de_AT"), "European Date"),
        item(fmtStyle(date, "en_US", 4, 0), "English"),
        item(fmtStyle(date, "de_AT", 4, 0), "German"),
        item(String(unix), "Unix Timestamp")
    ];
}

function formatDateTime(date, unix) {
    return [
        item(fmt(date, "yyyy-MM-dd'_'HH-mm", "en_US_POSIX"), "ISO DateTime"),
        item(fmt(date, "dd.MM.yyyy HH:mm", "de_AT"), "European DateTime"),
        item(fmtStyle(date, "en_US", 4, 1), "English"),
        item(fmtStyle(date, "de_AT", 4, 1), "German"),
        item(String(unix), "Unix Timestamp")
    ];
}