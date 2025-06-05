#!/bin/bash

# Music Discovery System Setup Script
# This script sets up the entire development and production environment

set -e

echo "🎵 Music Discovery System Setup"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Check if required tools are installed
check_dependencies() {
    print_header "Checking Dependencies"
    
    local missing_deps=()
    
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! command -v node &> /dev/null; then
        missing_deps+=("node")
    fi
    
    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi
    
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("pip3")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        print_error "Please install the missing dependencies and run this script again."
        exit 1
    fi
    
    print_status "All dependencies are installed ✓"
}

# Setup environment file
setup_environment() {
    print_header "Setting up Environment"
    
    if [ ! -f ".env" ]; then
        print_status "Creating .env file from template..."
        cp env.example .env
        print_warning "Please edit .env file with your actual API keys and configuration"
        print_warning "Required API keys:"
        echo "  - YouTube Data API v3"
        echo "  - Spotify API"
        echo "  - DeepSeek API"
        echo "  - Firecrawl API"
        echo "  - Supabase URL and Key"
        echo ""
        read -p "Press Enter after you've configured the .env file..."
    else
        print_status ".env file already exists ✓"
    fi
}

# Setup backend
setup_backend() {
    print_header "Setting up Backend"
    
    cd backend
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    print_status "Backend setup complete ✓"
    cd ..
}

# Setup frontend
setup_frontend() {
    print_header "Setting up Frontend"
    
    cd frontend
    
    # Install dependencies
    print_status "Installing Node.js dependencies..."
    npm install
    
    print_status "Frontend setup complete ✓"
    cd ..
}

# Setup database
setup_database() {
    print_header "Setting up Database"
    
    print_status "Database schema is ready in database-schema file"
    print_warning "Make sure to run the schema in your Supabase project:"
    echo "  1. Go to your Supabase dashboard"
    echo "  2. Navigate to SQL Editor"
    echo "  3. Copy and run the contents of 'database-schema' file"
    echo ""
    read -p "Press Enter after you've set up the database schema..."
}

# Build and start services
start_development() {
    print_header "Starting Development Environment"
    
    print_status "Starting services with Docker Compose..."
    docker-compose up -d redis
    
    print_status "Starting backend..."
    cd backend
    source venv/bin/activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    cd ..
    
    print_status "Starting frontend..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    
    print_status "Development environment started!"
    echo ""
    echo "🌐 Frontend: http://localhost:3000"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📊 API Docs: http://localhost:8000/docs"
    echo ""
    print_warning "Press Ctrl+C to stop all services"
    
    # Wait for interrupt
    trap "kill $BACKEND_PID $FRONTEND_PID; docker-compose down; exit" INT
    wait
}

# Production deployment
deploy_production() {
    print_header "Production Deployment"
    
    print_status "Building and starting production environment..."
    docker-compose -f docker-compose.prod.yml up -d --build
    
    print_status "Production environment deployed!"
    echo ""
    echo "🌐 Application: http://localhost"
    echo "📊 Monitoring: http://localhost:9090 (Prometheus)"
    echo "📈 Dashboards: http://localhost:3001 (Grafana)"
}

# Health check
health_check() {
    print_header "Health Check"
    
    print_status "Checking backend health..."
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_status "Backend is healthy ✓"
    else
        print_error "Backend health check failed ✗"
    fi
    
    print_status "Checking frontend..."
    if curl -f http://localhost:3000 &> /dev/null; then
        print_status "Frontend is accessible ✓"
    else
        print_error "Frontend is not accessible ✗"
    fi
}

# Main menu
show_menu() {
    echo ""
    echo "Choose an option:"
    echo "1) Full Development Setup"
    echo "2) Backend Setup Only"
    echo "3) Frontend Setup Only"
    echo "4) Start Development Environment"
    echo "5) Deploy Production Environment"
    echo "6) Health Check"
    echo "7) Exit"
    echo ""
}

# Main execution
main() {
    check_dependencies
    
    while true; do
        show_menu
        read -p "Enter your choice (1-7): " choice
        
        case $choice in
            1)
                setup_environment
                setup_database
                setup_backend
                setup_frontend
                print_status "Full setup complete! Use option 4 to start development environment."
                ;;
            2)
                setup_backend
                ;;
            3)
                setup_frontend
                ;;
            4)
                start_development
                ;;
            5)
                deploy_production
                ;;
            6)
                health_check
                ;;
            7)
                print_status "Goodbye! 👋"
                exit 0
                ;;
            *)
                print_error "Invalid option. Please choose 1-7."
                ;;
        esac
    done
}

# Run main function
main "$@" 