# A2A Shopping Assistant Demo

## Overview

This repository contains a demonstration of a conversational shopping assistant application for Android. The app showcases a modern, end-to-end user experience,
from natural language product discovery to a secure payment flow using Digital
Payment Credentials (DPC).

The core of the application is powered by the Google Generative AI SDK (Gemini),
 which drives the conversational agent. Communication between the application
 and the backend merchant services is handled using the A2A (App-to-App)
 protocol. For the payment process, the app integrates with Digital Payment
 Credentials (DPC) through the Android Credential Manager API to provide a
 seamless and secure transaction experience.

## Key Features

-   **Conversational AI:** A friendly and helpful shopping assistant powered by
 the Gemini model.
-   **Guided Shopping Flow:** A multi-turn conversational experience that
guides the user from product discovery to purchase confirmation.
-   **Digital Payment Credential (DPC) Integration:** A modern, secure payment
 flow using the Android Credential Manager that allows signing over the user's intent displayed on a trusted surface.
-   **A2A Protocol:** Demonstrates a standardized communication pattern between
 the user-facing app and a backend agent (in this case, a simulated merchant
 server).

## Executing the Example

### Setup

Complete these one-time setup steps before running the demo.

1.  **Configure Your API Key**

    You need a Google AI API key for the Gemini model to function. This key **must be placed in two locations**:

    1.  **For the Merchant Server:** Set the key as an environment variable in your terminal session:
        ```shell
        export GOOGLE_API_KEY="YOUR_API_KEY"
        ```

    2.  **For the Android App:** Create a file named `local.properties` in the Android project directory (`/samples/android/assistantA2A/`). Add your API key and Android SDK Path to this file:
        ```properties
        GEMINI_API_KEY="YOUR_API_KEY"

        # You can find this path in Android Studio under:
        # Settings > Languages & Frameworks > Android SDK
        sdk.dir=<path-to-your-android-sdk>
        ```

2.  **Set JAVA_HOME**

    The Gradle build requires a Java Development Kit (JDK), typically version 17. Android Studio bundles its own JDK, but your terminal needs the `JAVA_HOME` environment variable to find it. Set this variable to point to a valid JDK installation.

    For example, on macOS, if you have Android Studio installed, it might look like this:
    ```shell
    export JAVA_HOME=<path-to-your-jdk>
    ```

3.  **Python Environment**

    Ensure your environment meets the [Python sample prerequisites](http://github.com/payments-agentic-commerce/ap2/samples/python), including
     having tools like `uv` available.

4.  **Sideload the Digital Wallet App**

    This demo requires a separate digital wallet application ('CM Wallet')
    to be installed on the same device that holds the Digital Payment
    Credentials.

    TODO: [Link to CM Wallet App](https://drive.google.com/file/d/1N_mtKpyBARY_DPucdJqgmnXviOkmsYwP/view?usp=sharing)

5.  **Enable the Enhanced Payment Confirmation UI**

    To experience the most modern and secure payment flow, you must enable
    a required feature flag:

    **Enroll in the [Google Play Services Beta Program](https://developers.google.com/android/guides/beta-program):** Ensure the Google Account on your test
    device is enrolled.


### Execution

This repository includes a convenience script that builds the Android app,
installs it, launches it, and starts the local merchant server.

1.  Ensure all steps in the **Setup** section are complete.
2.  From the root of this repository, run the following command:

    ```bash
    bash samples/android/scenarios/digital-payment-credentials/run.sh
    ```


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
