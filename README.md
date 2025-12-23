# ASU Course Availability Monitor

A web application that monitors ASU course availability using Selenium and sends email notifications when seats become available.

## Features

- 🖥️ Web dashboard to view course status
- 🤖 Automated course checking every 2 minutes
- 📧 Email notifications when seats become available
- ☁️ Cloud database storage with Supabase
- 🐳 Docker containerized for easy deployment

## Deployment to Render

### Option 1: Using Render Dashboard

1. **Connect your GitHub repository** to Render
2. **Create a new Web Service** from your repository
3. **Configure the service**:
   - **Runtime**: Docker
   - **Dockerfile Path**: `./Dockerfile`
4. **Set Environment Variables**:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon key
   - `EMAIL_USER`: Your Gmail address
   - `EMAIL_PASSWORD`: Your Gmail app password
   - `NOTIFICATION_EMAIL`: Email to receive notifications

### Option 2: Using render.yaml

If you have the `render.yaml` file in your repository, Render will automatically detect and configure the service.

## Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd course-monitor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser** to `http://localhost:5000`

## API Endpoints

- `GET /` - Web dashboard
- `GET /api/courses` - Get current course status
- `GET /api/history/<course_number>` - Get history for a specific course
- `POST /api/start-monitoring` - Start the monitoring process
- `POST /api/stop-monitoring` - Stop the monitoring process
- `GET /api/status` - Get monitoring status

## Configuration

The courses to monitor are configured in `app.py`. Edit the `courses_to_check` list to add or remove courses.

## Security Notes

- Store sensitive credentials as environment variables
- Use Gmail app passwords for email notifications
- The application runs Selenium in headless Chrome for web scraping

## License

MIT License