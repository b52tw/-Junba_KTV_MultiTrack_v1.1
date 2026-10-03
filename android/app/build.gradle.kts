plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "tw.junba.ktvmultitrack"
    compileSdk = 35
    defaultConfig {
        applicationId = "tw.junba.ktvmultitrack"
        minSdk = 26
        targetSdk = 35
        versionCode = 11
        versionName = "1.1"
    }
    signingConfigs {
        create("releaseOptional") {
            val ks = project.findProperty("junbaKeystore") as String?
            if (!ks.isNullOrBlank()) {
                storeFile = file(ks)
                storePassword = project.findProperty("junbaStorePassword") as String?
                keyAlias = project.findProperty("junbaKeyAlias") as String?
                keyPassword = project.findProperty("junbaKeyPassword") as String?
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            val ks = project.findProperty("junbaKeystore") as String?
            if (!ks.isNullOrBlank()) signingConfig = signingConfigs.getByName("releaseOptional")
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
