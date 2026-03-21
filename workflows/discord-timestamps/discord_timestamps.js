#!/usr/bin/osascript -l JavaScript
ObjC.import('Foundation');

function run(argv) {
    var query = argv[0];

    // 1. Basic validation
    if (!query || query.length < 2) {
        return JSON.stringify({
            items: [{
                title: "Enter a date or time",
                subtitle: "Examples: 'tomorrow 4pm', 'in 5 mins', 'next Friday'",
                valid: false
            }]
        });
    }

    // 2. Setup Native Parser
    // passing $() acts as a proper 'nil' for the error parameter
    var detector = $.NSDataDetector.dataDetectorWithTypesError($.NSTextCheckingTypeDate, $());
    
    // 3. Perform Match
    var range = $.NSMakeRange(0, query.length);
    var matches = detector.matchesInStringOptionsRange(query, 0, range);

    // 4. Handle Invalid Dates
    if (matches.count == 0) {
        return JSON.stringify({
            items: [{
                title: "Date not recognized",
                subtitle: "Keep typing...",
                valid: false
            }]
        });
    }

    // Extract the date from the first match
    var date = matches.objectAtIndex(0).date;
    var unix = Math.floor(date.timeIntervalSince1970);

    // Helper: Formatters
    // UPDATED: Now matches Discord's rendering logic exactly
    function getPreview(dateObj, styleStr) {
        var f = $.NSDateFormatter.alloc.init;
        f.locale = $.NSLocale.currentLocale;
        
        if (styleStr === 't') { 
            f.dateStyle = 0; // None
            f.timeStyle = 1; // Short (16:20)
        }
        else if (styleStr === 'T') { 
            f.dateStyle = 0; // None
            f.timeStyle = 2; // Medium (16:20:30)
        }
        else if (styleStr === 'd') { 
            f.dateStyle = 1; // Short (20/04/2021)
            f.timeStyle = 0; // None
        }
        else if (styleStr === 'D') { 
            f.dateStyle = 3; // Long (20 April 2021)
            f.timeStyle = 0; // None
        }
        else if (styleStr === 'f') { 
            f.dateStyle = 3; // Long (20 April 2021)
            f.timeStyle = 1; // Short (16:20)
        }
        else if (styleStr === 'F') { 
            f.dateStyle = 4; // Full (Tuesday, 20 April 2021)
            f.timeStyle = 1; // Short (16:20)
        }
        
        return f.stringFromDate(dateObj).js;
    }

    function getRelativePreview(dateObj) {
        var diff = (dateObj.timeIntervalSince1970 - $.NSDate.date.timeIntervalSince1970);
        var r = $.NSRelativeDateTimeFormatter.alloc.init;
        return r.localizedStringFromTimeInterval(diff).js;
    }

    // 5. Build Items
    var formats = [
        { code: 'R', label: "Relative Time", preview: getRelativePreview(date) },
        { code: 'F', label: "Long Date & Time", preview: getPreview(date, 'F') },
        { code: 't', label: "Short Time", preview: getPreview(date, 't') },
        { code: 'D', label: "Long Date", preview: getPreview(date, 'D') },
        { code: 'f', label: "Short Date & Time", preview: getPreview(date, 'f') },
        { code: 'd', label: "Short Date", preview: getPreview(date, 'd') },
        { code: 'T', label: "Long Time", preview: getPreview(date, 'T') }
    ];

    var items = formats.map(function(fmt) {
        var discordTag = "<t:" + unix + ":" + fmt.code + ">";
        return {
            title: fmt.preview,
            subtitle: fmt.label + "   " + discordTag,
            arg: discordTag,
            icon: { path: "icon.png" },
            text: { copy: discordTag, largetype: discordTag }
        };
    });

    return JSON.stringify({ items: items });
}