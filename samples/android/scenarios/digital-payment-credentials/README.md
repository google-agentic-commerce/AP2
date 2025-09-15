# AP2 Sample: User Authorization using Digitial Payment Credentials

This sample demonstrates user authentication of a purchase using digital payment
credentials (DPC).

## Scenario

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

## Key Actors

This sample consists of:

*   **Shopping Agent:** An Android app that handles user's requests to shop.
*   **Merchant Agent:** An agent that handles product queries from the shopping
    agent and verifies the DPC signature.

## Key Features

-   Purchase with a **Digital Payment Credential (DPC):** A modern, secure
    payment flow using the Android Credential Manager that allows signing over
    the user's intent displayed on a trusted surface.

## Executing the Example

### Setup

1.  **Install Android Studio**

    Download Android Studio from the
    [official website](https://developer.android.com/studio) and install it.
    This will install the Android SDK, JDK, and all other necessary tools needed
    to build and run the Android app.

2.  **Obtain a Google API key from
    [Google AI Studio](https://aistudio.google.com/apikey)**

    Configure this key in the following locations:

    1.  Declare it as an environment variable. This is needed to start the
        merchant agent server.

        ```
        export GOOGLE_API_KEY=your_key
        ```

    1.  Add it to the local.properties file in
        [/samples/android/shopping_assistant](/samples/android/shopping_assistant).

        ```
        echo "GOOGLE_API_KEY=your_key" >> /samples/android/shopping_assistant
        ```

3.  **Add the Android SDK path to the local.properties file in
    [/samples/android/shopping_assistant](/samples/android/shopping_assistant).**

    You can find this path in Android Studio under `Settings > Languages &
    Frameworks > Android SDK`

    ~~~
    echo "sdk.dir=your_path >> /samples/android/shopping_assistant```
    ~~~

4.  **Set JAVA_HOME environment variable**

    The Java Development Kit (JDK) is typically installed with Android Studio,
    but does not set the JAVA_HOME environment variable. Be sure it is set.

    ```
    export JAVA_HOME=your_jdk_path
    ```

5.  **Ensure your environment meets
    the [Python sample prerequisites](../../../python).**

6.  **Install the Digital Wallet App (sideloaded)**

    This demo requires a separate digital wallet application ('CM Wallet') to be
    installed on the same device that holds the Digital Payment Credentials.

    TODO:
    [Link to CM Wallet App](https://drive.google.com/file/d/1N_mtKpyBARY_DPucdJqgmnXviOkmsYwP/view?usp=sharing)

    ```
    adb install <the-place-of-your-cm-app-apk>
    ```

7.  **Enable the Enhanced Payment Confirmation UI**

    To experience the most modern and secure payment flow, you must enable a
    required feature flag:

    **Enroll in the
    [Google Play Services Beta Program](https://developers.google.com/android/guides/beta-program):**
    Ensure the Google Account on your test device is enrolled.

### Execution

A convenience script is included to automatically build, install, and launch the
Android app, and start the local merchant server.

```sh
bash samples/android/scenarios/digital-payment-credentials/run.sh
```

## How to Use the App

1.  Ensure the local Merchant Agent server is running:

    ```
    curl http://localhost:8001/a2a/merchant_agent/.well-known/agent-card.json
    ```

2.  Launch the Shopping Assistant app on your device.

3.  In the app's settings screen, enter the URL for your local merchant server.
    The default URL will be `http://10.0.2.2:8001`.

4.  Click the **Connect** button. The app will fetch the A2A Agent Card from the
    server and initialize the chat session.

5.  You can now start a conversation with the shopping assistant. For example,
    try saying: "I'm looking for a new car."
