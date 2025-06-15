# Flask Strategic Dashboard

## Overview
The Flask Strategic Dashboard is a web application designed to provide insights into artist development, partnerships, and marketing analysis. It leverages a MongoDB database to fetch and display relevant data, offering a user-friendly interface for users to explore various metrics.

## Project Structure
```
flask-strategic-dashboard
├── app.py
├── requirements.txt
├── README.md
└── templates
    └── dashboard.html
```

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd flask-strategic-dashboard
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**
   Install the required packages listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure MongoDB**
   Ensure you have a MongoDB instance running and update the connection string in `app.py` with your MongoDB credentials.

5. **Run the Application**
   Start the Flask application:
   ```bash
   python app.py
   ```

6. **Access the Dashboard**
   Open your web browser and navigate to `http://127.0.0.1:5000/dashboard` to view the strategic dashboard.

## Functionality
- **Artist Development Metrics**: Analyze and visualize data related to artist performance, including song popularity and collaboration metrics.
- **Partnership Insights**: Explore data on featured artists and collaborations to understand partnership dynamics.
- **Marketing Analysis**: Gain insights into the effectiveness of marketing strategies through data visualization.

## Technologies Used
- Flask: A lightweight WSGI web application framework.
- MongoDB: A NoSQL database for storing and retrieving data.
- HTML/CSS/JavaScript: For building the user interface and ensuring interactivity.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.
