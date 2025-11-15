#!/bin/bash
# Setup script for local cron job to run book monitor daily

# Get the absolute path to the project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_PATH=$(which python3)

# Create log directory
mkdir -p "$SCRIPT_DIR/logs"

# Create the cron job command
# Run daily at 6 AM local time
CRON_COMMAND="0 6 * * * cd $SCRIPT_DIR && $PYTHON_PATH monitor.py --verbose >> $SCRIPT_DIR/logs/monitor_\$(date +\%Y\%m\%d).log 2>&1"

echo "=========================================="
echo "Book Monitor - Local Cron Job Setup"
echo "=========================================="
echo ""
echo "This will set up a cron job to run the book monitor daily at 6 AM."
echo ""
echo "Cron command to be added:"
echo "$CRON_COMMAND"
echo ""
echo "Required environment variables (add to crontab):"
echo "BREVO_API_KEY=your_api_key_here"
echo "SENDER_EMAIL=your_email@example.com"
echo "RECIPIENT_EMAIL=your_email@example.com"
echo "GOOGLE_SHEETS_ID=your_sheet_id_here"
echo ""
echo "To install:"
echo "1. Open crontab editor: crontab -e"
echo "2. Add environment variables at the top:"
echo "   BREVO_API_KEY=xkeysib-..."
echo "   SENDER_EMAIL=you@example.com"
echo "   RECIPIENT_EMAIL=you@example.com"
echo "   GOOGLE_SHEETS_ID=1wnGY6o-uRGw1..."
echo ""
echo "3. Add this line at the bottom:"
echo "   $CRON_COMMAND"
echo ""
echo "4. Save and exit"
echo ""
echo "To verify installation:"
echo "   crontab -l"
echo ""
echo "To view logs:"
echo "   tail -f $SCRIPT_DIR/logs/monitor_\$(date +%Y%m%d).log"
echo ""
echo "=========================================="
echo ""
read -p "Would you like me to open crontab editor now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Opening crontab editor..."
    echo "Remember to add the environment variables and cron command shown above!"
    sleep 3
    crontab -e
else
    echo "Skipped. You can run 'crontab -e' manually when ready."
fi
