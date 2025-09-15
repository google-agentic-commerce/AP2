# A2A Shopping Assistant Demo

## Overview

This repository contains a demonstration of a conversational shopping assistant
application for Android. The app showcases a modern, end-to-end user experience,
from natural language product discovery to a secure payment flow using Digital
Payment Credentials (DPC).

The core of the application is powered by the Google Generative AI SDK (Gemini),
which drives the conversational agent. Communication between the application and
the backend merchant services is handled using the A2A (App-to-App) protocol.
For the payment process, the app integrates with Digital Payment Credentials
(DPC) through the Android Credential Manager API to provide a seamless and
secure transaction experience.

## Key Features

-   **Conversational AI:** A friendly and helpful shopping assistant powered by
    the Gemini model.
-   **Guided Shopping Flow:** A multi-turn conversational experience that guides
    the user from product discovery to purchase confirmation.
-   **Digital Payment Credential (DPC) Integration:** A modern, secure payment
    flow using the Android Credential Manager that allows signing over the
    user's intent displayed on a trusted surface.
-   **A2A Protocol:** Demonstrates a standardized communication pattern between
    the user-facing app and a backend agent (in this case, a simulated merchant
    server).

## Demo Setup Instructions

To run this demo successfully, you will need to set up the Android application,
a local merchant server, and a digital wallet application.

### 1. Android Studio Project Setup

1.  Open the project in Android Studio.
2.  Create a new file in the root directory of the project named
    `local.properties`.
3.  Add your Google AI API key to the `local.properties` file. This key is
    required to use the Gemini model. `properties GEMINI_API_KEY="YOUR_API_KEY"`
4.  Sync the project with the Gradle files to ensure all dependencies are
    downloaded.
5.  Build and run the application on an Android device or emulator.

### 2. Start the Merchant Server

The application requires a local merchant server to be running to handle product
searches and payment processing. This scenario utilizes the merchant agent from
the project's Python samples

To start the merchant agent:

1. Ensure you meet the [Python sample prerequisites](http://github.com/payments-agentic-commerce/ap2/samples/python).
1. In a terminal, navigate to the root of the repository.
1. Setup your GOOGLE_API_KEY environment variable:

    ```
    export GOOGLE_API_KEY=your_key
    ```

1. Start the agent server:

    ```
    uv run --package ap2-samples python -m roles.merchant_agent
    ```

### 3. Sideload the Digital Wallet App

This demo requires a separate digital wallet application to be installed on the
same device. This app, named 'CM Wallet', acts as the user's wallet and holds
their Digital Payment Credentials.

TODO: [Link to CM Wallet App]

### 4. Enabling the Enhanced Payment Confirmation UI

To experience the most modern and secure payment flow, you must enable a feature
flag for an enhanced payment confirmation on a trusted surface UI. This requires
the following one-time setup steps:

1.  **Enroll in the
    [Google Play Services Beta Program](https://developers.google.com/android/guides/beta-program):**
    Ensure the Google Account on your test device is enrolled in the public beta
    program for Google Play services.
2.  **Join the Google Group:** TODO: Add instruction

After completing these steps, the feature flag will be enabled on your device,
and you will see the enhanced UI during the payment portion of the demo.

## How to Use the App

1.  Ensure the local merchant server is running.
2.  Launch the A2A Shopping Assistant app on your device.
3.  In the app's settings screen, enter the URL for your local merchant server.
    If you are running the server on your local machine and using an Android
    emulator, the default URL will be `http://10.0.2.2:8001`.
4.  Click the **Connect** button. The app will fetch the agent card from the
    server and initialize the chat session.
5.  You can now start a conversation with the shopping assistant. For example,
    try saying: "I'm looking for a new car."
