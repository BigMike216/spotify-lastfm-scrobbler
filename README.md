# Overview 

Its an script that helps to upload your old Spotify listening history to last.fm. <br><br>

## STEPS TO FOLOW 
<br><br>

**Step 1: Get Spotify History**

- Go to https://www.spotify.com/in-en/account/overview/ 
- Click on **Account privacy** and scroll down there u will get options to requst data 
- And you will get your Spotify History in few days in your email. <br><br>


**Step 2: Install python & VS Code**

- Go to https://www.python.org/downloads/ and install and run it.
- After installing open the terminal ( Windows+ R and type cmd and enter) and 
  in the type 
```
python --version
```
  to check if u have successfully installed python.
- Get VS code (optional but helpful for editing files) "https://code.visualstudio.com/download". <br><br>


**Step 3: Install Required Libraries**

- Go to Windows PowerShell and type 
```
pip install pylast pandas python-dotenv
```
  hit enter and it will be installed. <br><br>


**Step 4: Convert .json file to .csv part file**

1. Click on "<> Code" and download the ZIP file, then extract it.

2. After extraction, open the folder. You will find a folder with the same name. 
   Copy the innermost folder (containing all the actual files) and paste it in desktop.

3. Upload the Spotify history files in that desktop folder 
the files should look smt like this- 

   **StreamingHistory_music_0** 
   or 
   **Streaming_History_Audio_2024-2025_0**


4. Your folder should now look smt like this:
   <pre>
        📁 spotify-lastfm-scrobbler-master
        ├── .env 
        ├── converter.py
        ├── lastfm_scrobbler.py 
        ├── README.md
        ├── StreamingHistory_music_0.json
        ├── StreamingHistory_music_1.json
        └── ... (any other StreamingHistor_music files) 
   </pre>

5. Right click on the folder and open terminal.

6. In the terminal type this and hit enter.
```
python converter.py
```

7. Now your history files will will be converted to parts and saved in MusicCSV folder

> 💭 Note: 
> So Last.fm has a limit of around 2800-3000 scrobbles per day. Going above this might cause
> rate-limit errors or temporary submission blocks.
> (this has now prob changed to 650-700 scrobles per day)  
> This script automatically splits large CSV files into smaller parts.
> (each containing about 2800 [now 650] songs) 
> Also the Last.fm API supports sending multiple scrobbles in a single request 
> (up to 50 tracks per call).
> I have kept the part file limit to 650 but if u want to experiment by uploding more song then 
> go to converter.py (line no 13) and change 650 to 700 or any other number


**Step 5: The EXECUTION**

- Go to https://www.last.fm/api/account/create

- **Create an API account**
- You will get:
    API Key
    API Secret
    Username (your Last.fm username)
    Password (your Last.fm password)
- And replace that info in ".env" file.

- Your final folder shoul look smt like this

<pre>
    📁 spotify-lastfm-scrobbler-master
    ├── 📁 MusicCSV
    │   ├── part0.csv
    │   ├── part1.csv
    │   ├── part2.csv
    │   ├── ...
    │   └── part10.csv
    ├── .env       
    ├── converter.py
    ├── lastfm_scrobbler.py 
    └── README.md
</pre>

- Now right click again on the folder and open terminal and type this and hit ENTER. 
  ```
  python lastfm_scrobbler.py
  ```

- I hope it does work for ya all cuz it did for me. 
<br><br>

**DONT FORGET TO KEEP A 24H GAP AFTER UPLOADING EACH PART FILE TO LAST.FM** <br><br>

# Conclusion

Its an free alternative to universalscrobbler although its premium version is really cheap but 
people still have problem transferring files, and cancelling the subscription. 

So i made this script, 
its bit of a manual work work but does the job ^^

If you guys have any doubt join my discord server https://discord.gg/8FK38a2dR8 <br>
   ~ Big Mike
