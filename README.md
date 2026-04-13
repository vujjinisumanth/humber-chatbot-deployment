# InnovAI - Humber Program Matcher

InnovAI is a FastAPI-based project that scrapes Humber Polytechnic program data, stores it in Excel files, and provides a backend API to match user job descriptions or uploaded text files to relevant Humber programs. The project supports both Full-Time programs and Professional Learning (CPL) programs, and includes a monthly scheduler for refreshing the dataset automatically.[web:280][web:284]

## Features

- Scrape Humber Full-Time programs from the `explore-programs` site.
- Scrape Humber Professional Learning / CPL programs.
- Save scraped results into Excel files.
- Load the Full-Time dataset into a FastAPI backend.
- Match a job description against Humber programs.
- Apply filters such as credential, PGWP eligibility, start dates, program length, and work-integrated learning.
- Serve a frontend using FastAPI static files.
- Run monthly scheduled scraping using APScheduler.[web:280][web:285]

## Project Structure

```text
project/
├── backend/
│   ├── main.py
│   ├── scraper.py
│   ├── scheduler.py
│   ├── matcher.py
│   ├── requirements.txt
│   └── output/
│       ├── Humber_FullTime2.xlsx
│       └── Humber_CPL2.xlsx
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10 or newer is recommended.
- A virtual environment is recommended for local development.
- Install dependencies from `requirements.txt` before running the project.[web:286][web:289]

## Installation

Clone the repository and move into the project folder:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

Create and activate a virtual environment:

### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

## Required Python Packages

Your `requirements.txt` should include:

```txt
fastapi
uvicorn
pandas
openpyxl
requests
beautifulsoup4
lxml
tqdm
apscheduler
python-multipart
```

`python-multipart` is required because the FastAPI app accepts uploaded files and form data.[web:285]

## Running the Scraper

To scrape the latest Humber program data and generate the Excel outputs:

```bash
cd backend
python scraper.py
```

This creates:

- `output/Humber_FullTime2.xlsx`
- `output/Humber_CPL2.xlsx`

Make sure the Excel files are closed before re-running the scraper on Windows, because open Excel files can block overwriting.

## Running the API

Start the FastAPI backend locally:

```bash
cd backend
python main.py
```

Or run with uvicorn directly:

```bash
uvicorn main:app --reload
```

By default, the API runs at:

```text
http://127.0.0.1:8000
```

## Frontend

The frontend is served by FastAPI using static file mounting. When the backend is running, open:

```text
http://127.0.0.1:8000/
```

If you run the frontend separately on another local port like `3000`, `5173`, or `5500`, make sure the backend CORS settings allow that origin.[web:235][web:239]

## API Endpoints

### `GET /`
Serves the frontend `index.html`.

### `GET /health`
Returns backend health info and dataset status.

Example response:
```json
{
  "status": "running",
  "programs_loaded": 232,
  "scheduler_running": true
}
```

### `GET /filters`
Returns available credential options from the loaded dataset.

### `POST /match`
Matches a text job description or uploaded text file against Humber programs.

Accepted form fields:
- `jd_text`
- `file`
- `top_k`
- `cred_selected`
- `pgwp_choice`
- `start_choice`
- `length_selected`
- `wil_choice`

## Monthly Scheduler

The project includes a monthly scheduler using APScheduler. It is configured in `scheduler.py` and started by FastAPI during app startup.

Example monthly schedule:
- Run on day `1`
- At `02:00`

You can change these values in `scheduler.py`:

```python
MONTHLY_DAY = 1
MONTHLY_HOUR = 2
MONTHLY_MINUTE = 0
```

APScheduler is a better fit for monthly jobs than the simpler `schedule` library because it supports cron-style scheduling directly.[web:215][web:217]

## Notes

- The scraper is structured to work with Humber’s `explore-programs` pages.
- If Humber changes the page structure, the scraper selectors may need updates.
- The backend currently loads the Full-Time Excel file on startup. If the scheduler refreshes the file later, you may need to reload the dataset in memory if you want the API to use the newest data immediately.
- If running with multiple FastAPI workers, take care because more than one worker can start the scheduler job unless you separate scheduling into its own worker process.[web:230][web:234]

## Git Ignore Recommendation

Before pushing, make sure your `.gitignore` excludes:

- `.venv/`
- `__pycache__/`
- `.idea/`
- `.env`
- `output/`
- generated `.xlsx` and `.csv` files unless intentionally tracked.[web:253][web:254]

## Example Git Commands

After updating the project files:

```bash
git add .
git commit -m "Add scraper, scheduler, FastAPI backend, and project docs"
git push -u origin main
```

## Technologies Used

- Python
- FastAPI
- Requests
- BeautifulSoup
- Pandas
- OpenPyXL
- APScheduler
- Uvicorn[web:280][web:285]

## Future Improvements

- Add automatic dataset reload after scheduled scraping.
- Add logging for scraper failures and retries.
- Add deployment configuration for Render or another cloud platform.
- Add tests for matcher logic and scraper parsing.
- Add API docs and sample request payloads.

## License

This project is for educational and academic use.