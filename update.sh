echo "Updating subscriberBot..."
sudo systemctl stop subscriberBot
echo "Pulling changes..."
git pull
echo "Restarting subscriberBot..."
sudo systemctl start subscriberBot