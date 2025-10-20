import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import "bootstrap/dist/css/bootstrap.min.css";
import "./App.css";

// Components
import Navbar from "./components/Layout/Navbar";
import Footer from "./components/Layout/Footer";
import Home from "./components/Pages/Home";
import PetListings from "./components/Pages/PetListings";
import PetDetails from "./components/Pages/PetDetails";
import Login from "./components/Auth/Login";
import Register from "./components/Auth/Register";
import Dashboard from "./components/Dashboard/Dashboard";
import AddPet from "./components/Dashboard/AddPet";
import MyPets from "./components/Dashboard/MyPets";
import AdoptionRequests from "./components/Dashboard/AdoptionRequests";
import AdminPanel from "./components/Admin/AdminPanel";
import About from "./components/Pages/About";
import Contact from "./components/Pages/Contact";
import ProtectedRoute from "./components/Auth/ProtectedRoute";
import WelcomeBanner from "./WelcomeBanner";

// Context
import { AuthProvider } from "./contexts/AuthContext";
import { PetProvider } from "./contexts/PetContext";

function App() {
  return (
    <AuthProvider>
      <PetProvider>
        <Router>
          <div className="App">
            <Navbar />
            <main className="main-content">
              <WelcomeBanner name="Teacher Anna" />
              <Routes>
                {/* Public Routes */}
                <Route path="/" element={<Home />} />
                <Route path="/pets" element={<PetListings />} />
                <Route path="/pets/:id" element={<PetDetails />} />
                <Route path="/about" element={<About />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />

                {/* Protected Routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard/add-pet"
                  element={
                    <ProtectedRoute>
                      <AddPet />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard/my-pets"
                  element={
                    <ProtectedRoute>
                      <MyPets />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard/adoption-requests"
                  element={
                    <ProtectedRoute>
                      <AdoptionRequests />
                    </ProtectedRoute>
                  }
                />

                {/* Admin Routes */}
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute adminRequired={true}>
                      <AdminPanel />
                    </ProtectedRoute>
                  }
                />
              </Routes>
            </main>
            <Footer />
          </div>
        </Router>
      </PetProvider>
    </AuthProvider>
  );
}

export default App;
