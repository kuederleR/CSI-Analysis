#include <iostream>  // For standard input/output operations (e.g., std::cout, std::cerr)
#include <fstream>   // For file stream operations (e.g., std::ofstream)
#include <vector>    // Not strictly needed here, but good for general data handling
#include <random>    // For random number generation (std::random_device, std::mt19937, std::uniform_real_distribution)
#include <string>    // For string manipulation (std::string)
#include <cstdio>    // For popen/pclose (to execute gnuplot as a separate process) and std::remove
#include <thread>    // For std::this_thread::sleep_for to control update rate
#include <chrono>    // For std::chrono::milliseconds and other time utilities

// Define popen and pclose for cross-platform compatibility
// On Windows, these functions are typically prefixed with an underscore.
#ifdef _WIN32
#define popen _popen
#define pclose _pclose
#endif

int main()
{
    // Define the number of random points we want to generate
    const int numberOfPoints = 500;
    // Define the filename for our temporary data file that gnuplot will read
    const std::string dataFileName = "random_points_3d.dat";
    // Define the desired update frequency in Hertz (Hz)
    const int updateFrequencyHz = 20; // Graph will update 2 times per second
    // Calculate the interval in milliseconds between updates
    const std::chrono::milliseconds updateInterval(1000 / updateFrequencyHz);

    // --- 1. Set Up Random Number Generation ---
    // std::random_device provides non-deterministic random numbers (if available)
    std::random_device rd;
    // std::mt19937 is a Mersenne Twister pseudo-random number generator, seeded by rd
    std::mt19937 eng(rd());

    // Distribution for X and Y coordinates (wider range, e.g., -10.0 to 10.0)
    std::uniform_real_distribution<> xy_distr(-10.0, 10.0);
    // Distribution for Z coordinates (much smaller range to create less diversity,
    // making points cluster around a plane, simulating a rough surface)
    std::uniform_real_distribution<> z_distr(-5.0, 5.0); // Z-range significantly reduced

    // --- 2. Open Pipe to Gnuplot ---
    // Open a pipe to the gnuplot executable.
    // "w" mode means we can write commands to gnuplot's standard input.
    // IMPORTANT: Removed "-persistent" flag. Now gnuplot will exit when its input pipe closes.
    FILE* gnuplotPipe = popen("gnuplot", "w"); // Removed -persistent
    if (!gnuplotPipe)
    {
        std::cerr << "Error: Could not open gnuplot pipe. Make sure gnuplot is installed and in your system's PATH." << std::endl;
        return 1; // Indicate an error if gnuplot cannot be launched
    }

    // --- 3. Send Initial Gnuplot Configuration Commands ---
    // These commands set up the plot environment and only need to be sent once.
    // 'set terminal qt': This is the interactive terminal.
    // 'nomenubar', 'notoolbar', 'noborder', 'noenhanced': These remove GUI elements.
    // 'close_on_exit': This is a gnuplot internal command that ensures the current terminal
    //                  window is explicitly closed when the gnuplot process exits.
    fprintf(gnuplotPipe, "set terminal qt nomenubar notoolbar noborder noenhanced close_on_exit\n");
    fprintf(gnuplotPipe, "set title 'Dynamically Updating Rough 3D Surface'\n");
    fprintf(gnuplotPipe, "set xlabel 'X-axis'\n");
    fprintf(gnuplotPipe, "set ylabel 'Y-axis'\n");
    fprintf(gnuplotPipe, "set zlabel 'Z-axis'\n");

    // Configure Gnuplot for surface plotting from scattered data:
    // 'set dgrid3d': This command interpolates scattered 3D data onto a regular grid.
    // The arguments (e.g., 50,50) specify the resolution of the grid (50x50 in this case).
    // This is essential to create a "surface" from non-gridded random points.
    fprintf(gnuplotPipe, "set dgrid3d 50,50\n");
    // 'set pm3d': This enables the palette-mapped 3D drawing mode, which draws a colored surface.
    // Without 'map', it creates a true 3D surface.
    fprintf(gnuplotPipe, "set pm3d\n");
    // 'set hidden3d': This hides lines or parts of the surface that would be obscured by other parts,
    // making the 3D representation clearer and more realistic.
    fprintf(gnuplotPipe, "set hidden3d\n");
    // Optionally set a custom palette for surface coloring (e.g., from blue to red based on Z value)
    fprintf(gnuplotPipe, "set palette defined (0 'blue', 1 'green', 2 'yellow', 3 'red')\n");

    fprintf(gnuplotPipe, "set grid\n"); // Add a grid for better visual guidance
    // Explicitly set the ranges for axes. Z-range is adjusted for less diversity.
    fprintf(gnuplotPipe, "set xrange [-10:10]\n");
    fprintf(gnuplotPipe, "set yrange [-10:10]\n");
    fprintf(gnuplotPipe, "set zrange [-1.5:1.5]\n"); // Slightly wider than z_distr for padding
    // Set an initial view angle for a better perspective on the surface
    fprintf(gnuplotPipe, "set view 60, 30, 1, 1\n"); // view_rot_x, view_rot_z, scale, z_scale

    // --- 4. Start Dynamic Update Loop ---
    std::cout << "Starting dynamic rough surface generation and plotting (2 Hz update rate)..." << std::endl;
    std::cout << "To stop, close the gnuplot window. This will also terminate this program." << std::endl;
    std::cout << "You can also press Ctrl+C in this console to stop." << std::endl;


    // This loop will run indefinitely, continuously updating the plot.
    while (true)
    {
        // --- 4a. Generate New Random 3D Points ---
        // Open the data file for writing. std::ofstream by default truncates (clears) the file
        // if it exists, ensuring we write a fresh set of points each time.
        std::ofstream outFile(dataFileName);
        if (!outFile.is_open())
        {
            std::cerr << "Error: Could not open data file " << dataFileName << " for writing." << std::endl;
            break; // Exit the loop if we can't write the data
        }

        // Write the new set of random points to the file
        for (int i = 0; i < numberOfPoints; ++i)
        {
            double x = xy_distr(eng);
            double y = xy_distr(eng);
            double z = z_distr(eng); // Use the new, smaller range for Z
            outFile << x << " " << y << " " << z << std::endl;
        }
        outFile.close(); // Important: Close the file immediately after writing

        // --- 4b. Tell Gnuplot to Replot as a Surface ---
        // 'splot' is used for 3D plots. With 'set dgrid3d' and 'set pm3d' configured,
        // gnuplot will now interpret this scattered data to create a colored 3D surface.
        // Check the return value of fprintf to detect if the pipe is broken (gnuplot window closed).
        int bytesWritten = fprintf(gnuplotPipe, "splot '%s' using 1:2:3 title 'Rough Surface' with pm3d\n", dataFileName.c_str());
        fflush(gnuplotPipe); // Crucial: force buffered commands to be sent to gnuplot

        // If fprintf returns a negative value or ferror indicates an error, the pipe is likely broken,
        // meaning the gnuplot process or its window has terminated.
        if (bytesWritten < 0 || ferror(gnuplotPipe))
        {
            std::cout << "Gnuplot window detected as closed or pipe broken. Exiting program." << std::endl;
            break; // Exit the main loop
        }

        // --- 4c. Pause for the Specified Interval ---
        // This makes the program wait for the calculated 'updateInterval' before the next iteration,
        // controlling the update frequency to 2Hz.
        std::this_thread::sleep_for(updateInterval);
    }

    // --- 5. Clean Up ---
    // Close the pipe to gnuplot. This also helps ensure gnuplot finishes gracefully.
    pclose(gnuplotPipe); // This will also cause the gnuplot process to terminate now

    // Remove the temporary data file from the disk.
    // std::remove returns 0 on success, non-zero on failure.
    if (std::remove(dataFileName.c_str()) != 0)
    {
        std::cerr << "Error: Failed to delete temporary data file: " << dataFileName << std::endl;
    }
    else
    {
        std::cout << "Successfully cleaned up temporary data file: " << dataFileName << std::endl;
    }

    std::cout << "Program terminated successfully." << std::endl;
    return 0; // Indicate successful program execution
}
