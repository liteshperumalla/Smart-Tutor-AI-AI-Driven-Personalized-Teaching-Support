#!/bin/bash
# Convert old .ppt files that were renamed to .pptx

FILES=(
    "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/Modules/Module 5/Lesson Five- Data cleaning and preprocessing.pptx"
    "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/Modules/Module 12/INFO 5731 - Lesson nine - Sentiment analysis-1.pptx"
    "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/Modules/Module 6/Lesson six-Feature extraction from text-2024.pptx"
    "/Users/liteshperumalla/Desktop/Files/masters/Smart AI Tutor/Modules/Module 8/Lesson Seven- Information Extraction from Textual Data_Updated-02262024 (1).pptx"
)

echo "Converting 4 PowerPoint files using Keynote..."

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Converting: $(basename "$file")"
        
        # Use osascript to open in Keynote and export as PPTX
        osascript <<APPLESCRIPT
tell application "Keynote"
    activate
    open POSIX file "$file"
    delay 2
    tell front document
        export to POSIX file "${file%.pptx}_converted.pptx" as Microsoft PowerPoint
    end tell
    close front document without saving
end tell
APPLESCRIPT
        
        # Replace original with converted version
        if [ -f "${file%.pptx}_converted.pptx" ]; then
            mv "${file%.pptx}_converted.pptx" "$file"
            echo "  ✅ Converted successfully"
        else
            echo "  ✗ Conversion failed"
        fi
    else
        echo "File not found: $file"
    fi
done

echo ""
echo "✅ Conversion complete!"
echo "Now run: python3 process_renamed_files.py"
