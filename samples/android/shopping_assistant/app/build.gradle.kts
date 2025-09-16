import java.io.FileInputStream
import java.util.Properties

// File: app/build.gradle.kts (Module: app)

plugins {
  id("com.android.application")
  id("org.jetbrains.kotlin.android")
  id("org.jetbrains.kotlin.plugin.serialization")
}

// Create a properties object
val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")

if (localPropertiesFile.exists()) {
  localProperties.load(FileInputStream(localPropertiesFile))
}

android {
  namespace = "com.example.a2achatassistant"
  compileSdk = 35

  defaultConfig {
    applicationId = "com.example.a2achatassistant"
    minSdk = 26
    targetSdk = 35
    versionCode = 1
    versionName = "1.0"
    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    vectorDrawables { useSupportLibrary = true }
    val apiKey: String = localProperties.getProperty("GEMINI_API_KEY") ?: ""
    buildConfigField("String", "GEMINI_API_KEY", "\"$apiKey\"")
  }

  buildTypes {
    release {
      isMinifyEnabled = false
      proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
    }
  }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_1_8
    targetCompatibility = JavaVersion.VERSION_1_8
  }
  kotlinOptions { jvmTarget = "1.8" }
  buildFeatures {
    compose = true
    buildConfig = true
  }
  composeOptions {
    // ✅ FIXED: Updated Compose Compiler to match Kotlin 1.9.22
    kotlinCompilerExtensionVersion = "1.5.10"
  }
  packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

dependencies {
  // Core Android & Jetpack
  implementation("androidx.navigation:navigation-compose:2.7.7")
  implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.6.0")
  implementation("io.ktor:ktor-client-cio:2.3.11")
  implementation("androidx.datastore:datastore-preferences:1.1.1")
  implementation("androidx.core:core-ktx:1.12.0")
  implementation("com.google.code.gson:gson:2.10.1")
  implementation("androidx.credentials:credentials:1.5.0")
  implementation("androidx.credentials:credentials-play-services-auth:1.5.0")
  implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
  implementation("androidx.activity:activity-compose:1.8.2")
  implementation(platform("androidx.compose:compose-bom:2024.02.02"))
  implementation("androidx.compose.ui:ui")
  implementation("androidx.compose.ui:ui-graphics")
  implementation("androidx.compose.ui:ui-tooling-preview")
  implementation("androidx.compose.material3:material3")

  implementation("io.ktor:ktor-client-okhttp:2.3.11")

  // ViewModel & LiveData for state management
  implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
  implementation("androidx.lifecycle:lifecycle-runtime-compose:2.7.0")

  // Google Generative AI (Gemini)

  // Ktor for Networking
  implementation("io.ktor:ktor-client-core:2.3.8")
  implementation("io.ktor:ktor-client-android:2.3.8")
  implementation("io.ktor:ktor-client-content-negotiation:2.3.8")
  implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.8")
  implementation("io.ktor:ktor-client-logging:2.3.8")

  // Kotlinx Serialization
  implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

  // Coroutines
  implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

  // Icons
  implementation("androidx.compose.material:material-icons-extended:1.6.3")
  implementation(libs.generativeai)
  implementation(libs.common)

  // Test Dependencies
  testImplementation("junit:junit:4.13.2")
  androidTestImplementation("androidx.test.ext:junit:1.1.5")
  androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
  androidTestImplementation(platform("androidx.compose:compose-bom:2024.02.02"))
  androidTestImplementation("androidx.compose.ui:ui-test-junit4")
  debugImplementation("androidx.compose.ui:ui-tooling")
  debugImplementation("androidx.compose.ui:ui-test-manifest")
}
