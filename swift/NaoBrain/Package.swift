// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NaoBrain",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "NaoBrain", targets: ["NaoBrain"])
    ],
    targets: [
        .executableTarget(
            name: "NaoBrain",
            path: "Sources/NaoBrain"
        )
    ]
)
