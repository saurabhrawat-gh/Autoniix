// Command production starts the Go Temporal worker for the "video-production"
// task queue. It registers only workflow types; activities are handled by
// the Python worker on the same queue.
package main

import (
	"log"
	"os"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	"github.com/autoniix/autoniix/go/workflows"
)

func main() {
	temporalHost := os.Getenv("TEMPORAL_HOST")
	if temporalHost == "" {
		temporalHost = "temporal:7233"
	}
	namespace := os.Getenv("TEMPORAL_NAMESPACE")
	if namespace == "" {
		namespace = "default"
	}

	c, err := client.Dial(client.Options{
		HostPort:  temporalHost,
		Namespace: namespace,
	})
	if err != nil {
		log.Fatalf("unable to connect to Temporal: %v", err)
	}
	defer c.Close()

	w := worker.New(c, "video-production", worker.Options{})

	// Register Go workflow definitions.
	// Python activity worker handles all activities on the same task queue.
	w.RegisterWorkflow(workflows.VideoProductionWorkflow)

	log.Printf("go-worker-production: listening on task queue=video-production namespace=%s host=%s", namespace, temporalHost)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("worker exited with error: %v", err)
	}
}
